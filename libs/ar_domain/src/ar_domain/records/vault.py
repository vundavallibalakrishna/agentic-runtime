"""Evidence capture and verification. Spec: docs/03-specs/21-records-governance.md §1."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode, NotFoundError, PayloadTooLargeError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.files.logic import MAX_UPLOAD_BYTES
from ar_domain.records.access import audit, missing, own, public, require
from ar_domain.records.crypto import public_pem, sign_manifest, signing_material, verify_manifest
from ar_domain.records.memory import blobs, bucket

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

_METHODS = frozenset({"api", "tool_call", "upload", "browser_screenshot", "sandbox", "run_record"})
_SIGNED = (
    "id",
    "tenant_id",
    "content_sha256",
    "size_bytes",
    "media_type",
    "collected_at",
    "source_system",
    "collection_method",
    "collector_principal_type",
    "collector_principal_id",
    "collector_run_id",
    "collector_tool_call_id",
    "provenance",
)


class EvidenceBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def capture(
        self,
        actor: Actor,
        payload: dict[str, object],
        data: bytes,
        *,
        idempotency_key: str = "",
    ) -> dict[str, object]:
        require(actor, "evidence:capture")
        if actor.kind == "guest":
            raise ArError(ErrorCode.GUEST_FORBIDDEN, "guest_forbidden")
        if len(data) > MAX_UPLOAD_BYTES:
            raise PayloadTooLargeError("evidence object is too large")
        method = str(payload.get("collection_method") or "api")
        if method not in _METHODS:
            raise ArError(ErrorCode.VALIDATION_FAILED, "collection_method is invalid")
        existing = self._idempotent(actor, idempotency_key)
        if existing is not None:
            return self._summary(existing, full=True)
        if payload.get("tsa_fail") is True or self._tsa_required_and_down():
            raise ArError(ErrorCode.TSA_UNAVAILABLE, "tsa_unavailable")
        self._drop_orphan(idempotency_key)
        item_id = new_id()
        now = utcnow()
        digest = hashlib.sha256(data).hexdigest()
        raw_provenance = payload.get("provenance")
        provenance: dict[str, object] = raw_provenance if isinstance(raw_provenance, dict) else {}
        principal = "service_account" if actor.kind == "service_account" else "user"
        body = {
            "id": str(item_id),
            "tenant_id": str(actor.tenant_id),
            "content_sha256": digest,
            "size_bytes": len(data),
            "media_type": str(payload.get("media_type") or "application/octet-stream"),
            "collected_at": now.isoformat(),
            "source_system": str(payload.get("source_system") or "api"),
            "collection_method": method,
            "collector_principal_type": principal,
            "collector_principal_id": str(actor.user_id),
            "collector_run_id": _opt_str(payload.get("collector_run_id")),
            "collector_tool_call_id": _opt_str(payload.get("collector_tool_call_id")),
            "provenance": {str(key): value for key, value in provenance.items()},
        }
        key_id, key = signing_material(self.store)
        signature, manifest_sha = sign_manifest(key, _signed(body))
        days = int(os_lock_days())
        row = {
            "id": item_id,
            "tenant_id": actor.tenant_id,
            "status": "sealed",
            "content_sha256": digest,
            "size_bytes": len(data),
            "media_type": body["media_type"],
            "storage_key": f"tenants/{actor.tenant_id}/evidence/{item_id}",
            "worm_locked_until": now + timedelta(days=days),
            "rfc3161_token": None,
            "signature": signature,
            "signature_key_id": key_id,
            "manifest_sha256": manifest_sha,
            "source_system": body["source_system"],
            "collection_method": method,
            "collected_at": now,
            "collector_run_id": _opt_uuid(payload.get("collector_run_id")),
            "collector_tool_call_id": _opt_uuid(payload.get("collector_tool_call_id")),
            "collector_principal_type": principal,
            "collector_principal_id": actor.user_id,
            "provenance": body["provenance"],
            "classification": "internal",
            "legal_hold": False,
            "retention_class": "evidence_item",
            "created_at": now,
            "idempotency_key": idempotency_key,
            "signed": body,
        }
        blobs(self.store, "evidence")[item_id] = data
        bucket(self.store, "evidence")[item_id] = row
        event_id = audit(
            self.store,
            actor,
            "evidence.captured",
            "evidence_item",
            item_id,
            {"content_sha256": digest, "source_system": body["source_system"]},
        )
        self._custody(actor, item_id, "captured", {}, event_id)
        return self._summary(row, full=True)

    def list_items(
        self,
        actor: Actor,
        *,
        source_system: str = "",
        collection_method: str = "",
        query: str = "",
    ) -> list[dict[str, object]]:
        require(actor, "evidence:read")
        rows = []
        for row in bucket(self.store, "evidence").values():
            if not own(row, actor.tenant_id):
                continue
            if source_system and row.get("source_system") != source_system:
                continue
            if collection_method and row.get("collection_method") != collection_method:
                continue
            if query and query.lower() not in _haystack(row):
                continue
            rows.append(self._summary(row, full=False))
        rows.sort(key=lambda item: str(item.get("collected_at") or ""), reverse=True)
        return rows

    def get(self, actor: Actor, item_id: uuid.UUID) -> dict[str, object]:
        row = self._visible(actor, item_id, write=False)
        return self._summary(row, full=True)

    def content(self, actor: Actor, item_id: uuid.UUID) -> tuple[dict[str, object], bytes]:
        row = self._visible(actor, item_id, write=True)
        data = blobs(self.store, "evidence").get(item_id)
        if not isinstance(data, bytes):
            raise NotFoundError()
        event_id = audit(
            self.store,
            actor,
            "evidence.accessed",
            "evidence_item",
            item_id,
            {"watermarked": actor.kind == "guest"},
        )
        self._custody(actor, item_id, "accessed", {"watermarked": actor.kind == "guest"}, event_id)
        return row, data

    def verify(self, actor: Actor, item_id: uuid.UUID) -> dict[str, object]:
        row = self._visible(actor, item_id, write=False)
        if not actor.has("evidence:read") and actor.kind != "guest":
            raise NotFoundError()
        data = blobs(self.store, "evidence").get(item_id, b"")
        digest_ok = hashlib.sha256(data).hexdigest() == row.get("content_sha256")
        signed = row.get("signed")
        key_id, key = signing_material(self.store)
        signature_ok = False
        if isinstance(signed, dict) and row.get("signature_key_id") == key_id:
            signature_ok = verify_manifest(
                public_pem(key), _signed(signed), str(row.get("signature"))
            )
        locked = row.get("worm_locked_until")
        lock_ok = bool(row.get("legal_hold")) or (
            hasattr(locked, "timestamp") and locked > utcnow()  # type: ignore[operator]
        )
        checks = [
            {"name": "sha256", "ok": digest_ok, "detail": "content hash"},
            {"name": "signature", "ok": signature_ok, "detail": "ed25519 manifest"},
            {"name": "object_lock", "ok": lock_ok, "detail": "retain or legal hold"},
        ]
        valid = all(bool(item["ok"]) for item in checks)
        event_id = audit(
            self.store, actor, "evidence.verified", "evidence_item", item_id, {"valid": valid}
        )
        self._custody(actor, item_id, "verified", {"valid": valid}, event_id)
        return {"valid": valid, "checks": checks}

    def custody(self, actor: Actor, item_id: uuid.UUID) -> list[dict[str, object]]:
        self._visible(actor, item_id, write=False)
        rows = [
            public(row)
            for row in bucket(self.store, "custody").values()
            if row.get("evidence_item_id") == item_id and own(row, actor.tenant_id)
        ]
        rows.sort(key=lambda item: str(item.get("created_at") or ""))
        return rows

    def _visible(self, actor: Actor, item_id: uuid.UUID, *, write: bool) -> dict[str, object]:
        row = bucket(self.store, "evidence").get(item_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            missing()
        if actor.kind == "guest":
            if not _guest_can_see(self.store, actor, item_id):
                missing()
            return row
        permission = "evidence:export" if write else "evidence:read"
        if not actor.has(permission) and row.get("collector_principal_id") != actor.user_id:
            missing()
        return row

    def _summary(self, row: dict[str, object], *, full: bool) -> dict[str, object]:
        body = public(row)
        brief = {
            "id": body.get("id"),
            "content_sha256": body.get("content_sha256"),
            "size_bytes": body.get("size_bytes"),
            "media_type": body.get("media_type"),
            "source_system": body.get("source_system"),
            "collection_method": body.get("collection_method"),
            "collected_at": body.get("collected_at"),
            "legal_hold": body.get("legal_hold"),
            "status": body.get("status"),
        }
        if not full:
            return brief
        brief.update(
            {
                "signature_key_id": body.get("signature_key_id"),
                "worm_locked_until": body.get("worm_locked_until"),
                "rfc3161": body.get("rfc3161_token") is not None,
                "collector_principal_type": body.get("collector_principal_type"),
                "collector_principal_id": body.get("collector_principal_id"),
                "collector_run_id": body.get("collector_run_id"),
                "collector_tool_call_id": body.get("collector_tool_call_id"),
                "provenance": body.get("provenance") or {},
                "storage_key": body.get("storage_key"),
            }
        )
        return brief

    def _custody(
        self,
        actor: Actor,
        item_id: uuid.UUID,
        action: str,
        detail: dict[str, object],
        event_id: int,
    ) -> None:
        row_id = new_id()
        bucket(self.store, "custody")[row_id] = {
            "id": row_id,
            "tenant_id": actor.tenant_id,
            "evidence_item_id": item_id,
            "action": action,
            "actor_principal_type": "guest" if actor.kind == "guest" else "user",
            "actor_principal_id": actor.user_id,
            "detail": detail,
            "audit_event_id": event_id,
            "created_at": utcnow(),
        }

    def _idempotent(self, actor: Actor, key: str) -> dict[str, object] | None:
        if not key:
            return None
        for row in bucket(self.store, "evidence").values():
            if own(row, actor.tenant_id) and row.get("idempotency_key") == key:
                return row
        return None

    def _drop_orphan(self, key: str) -> None:
        if not key:
            return
        orphans = bucket(self.store, "orphans")
        orphan = orphans.pop(key, None)
        if isinstance(orphan, dict):
            blobs(self.store, "evidence").pop(orphan.get("id"), None)

    def _tsa_required_and_down(self) -> bool:
        settings = getattr(self.store, "tenant_settings", {})
        row = settings.get(next(iter(settings), None)) if isinstance(settings, dict) else None
        evidence = row.get("evidence") if isinstance(row, dict) else None
        if isinstance(evidence, dict) and evidence.get("tsa_enabled") is True:
            return evidence.get("tsa_ok") is not True
        return False


def park_orphan(store: Any, key: str, item_id: uuid.UUID, data: bytes) -> None:
    """Remember an object written before the row insert, so a retry can delete it."""
    blobs(store, "evidence")[item_id] = data
    bucket(store, "orphans")[key] = {"id": item_id}


def _signed(body: dict[str, object]) -> dict[str, JsonValue]:
    signed: dict[str, JsonValue] = {}
    for key in _SIGNED:
        value = body.get(key)
        if isinstance(value, str | int | float | bool) or value is None:
            signed[key] = value
        elif isinstance(value, dict):
            signed[key] = {str(item): _plain(inner) for item, inner in value.items()}
        else:
            signed[key] = str(value) if value is not None else None
    return signed


def _plain(value: object) -> JsonValue:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _opt_str(value: object) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _opt_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        return uuid.UUID(value)
    return None


def _haystack(row: dict[str, object]) -> str:
    provenance = row.get("provenance")
    note = provenance.get("note") if isinstance(provenance, dict) else ""
    return f"{row.get('source_system')} {note}".lower()


def _guest_can_see(store: Any, actor: Actor, item_id: uuid.UUID) -> bool:
    from ar_domain.identity.guests import guest_allows  # noqa: PLC0415

    return guest_allows(store, actor, "evidence", item_id)


def os_lock_days() -> int:
    import os  # noqa: PLC0415

    raw = os.environ.get("AR_EVIDENCE_DEFAULT_LOCK_DAYS", "").strip()
    return int(raw) if raw else 2555
