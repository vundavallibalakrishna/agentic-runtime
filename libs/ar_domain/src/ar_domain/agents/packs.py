"""Content packs. Spec: docs/03-specs/05-agent-registry.md §10.

Declarative packs install through the bundle importer. A manifest that sets
``extension`` is refused until pack migrations exist. ``dropSchema`` is the
same refusal.
"""

import base64
import hashlib
import uuid
from typing import TYPE_CHECKING, Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import JsonValue, ValidationError

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.jcs import canonical_json
from ar_common.time import utcnow
from ar_contracts.definitions import ContentPack
from ar_domain.bundles.import_ import import_bundle

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def manifest_digest(manifest: dict[str, object]) -> tuple[str, bytes]:
    """Hex and raw SHA-256 of the JCS encoding."""
    raw = hashlib.sha256(canonical_json(cast("JsonValue", manifest))).digest()
    return raw.hex(), raw


def verify_signature(public_pem: str, signature: str, digest: bytes) -> bool:
    """Ed25519 over the raw SHA-256 digest. ``signature`` is standard base64."""
    key = load_pem_public_key(public_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        return False
    try:
        key.verify(base64.b64decode(signature), digest)
    except InvalidSignature, ValueError:
        return False
    return True


def _result_rows(payload: dict[str, object]) -> list[object]:
    rows = payload.get("results")
    return list(rows) if isinstance(rows, list) else []


def _semver(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise ArError(ErrorCode.VALIDATION_FAILED, "version must be major.minor.patch")
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise ArError(ErrorCode.VALIDATION_FAILED, "version must be major.minor.patch") from exc


def _audit(
    store: Any,
    actor: Actor,
    action: str,
    target_id: str,
    detail: dict[str, object],
    *,
    outcome: str = "success",
) -> None:
    store.audit_log.append(
        {
            "tenant_id": str(actor.tenant_id),
            "actor_id": str(actor.user_id),
            "action": action,
            "target_type": "pack",
            "target_id": target_id,
            "detail": detail,
            "outcome": outcome,
        }
    )


class PackService:
    """Install, upgrade and uninstall declarative packs."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def _check_signature(
        self, actor: Actor, manifest: dict[str, object], signature: str | None, key_id: str | None
    ) -> tuple[str, str]:
        digest_hex, digest = manifest_digest(manifest)
        if not self.store.pack_signature_required and not signature:
            return digest_hex, ""
        public = self.store.pack_trusted_keys.get(key_id or "")
        if (
            not signature
            or not key_id
            or not isinstance(public, str)
            or not verify_signature(public, signature, digest)
        ):
            _audit(
                self.store,
                actor,
                "pack.signature_rejected",
                str(manifest.get("metadata")),
                {},
                outcome="failure",
            )
            raise ArError(ErrorCode.PACK_SIGNATURE_INVALID, "pack signature is invalid")
        return digest_hex, key_id

    def _parsed(self, manifest: dict[str, object]) -> ContentPack:
        try:
            return ContentPack.model_validate(manifest)
        except ValidationError as exc:
            raise ArError(ErrorCode.VALIDATION_FAILED, "manifest is invalid") from exc

    def list_packs(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            self._out(row)
            for row in self.store.packs.values()
            if row.get("tenant_id") == actor.tenant_id and row.get("status") == "installed"
        ]
        rows.sort(key=lambda item: str(item.get("pack_id")))
        return rows

    def get(self, actor: Actor, pack_id: str) -> dict[str, object]:
        row = self._current(actor, pack_id)
        body = self._out(row)
        body["resources"] = [
            {
                "kind": item.get("kind"),
                "slug": item.get("slug"),
                "resource_id": str(item.get("resource_id")),
            }
            for item in self.store.pack_resources.values()
            if item.get("pack_row_id") == row["id"]
        ]
        return body

    def install(
        self,
        actor: Actor,
        manifest: dict[str, object],
        *,
        signature: str | None,
        key_id: str | None,
    ) -> dict[str, object]:
        if not actor.has("packs:manage") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission packs:manage")
        parsed = self._parsed(manifest)
        digest_hex, used_key = self._check_signature(actor, manifest, signature, key_id)
        if parsed.spec.extension is not None:
            raise ArError(ErrorCode.EXTENSION_UNAVAILABLE, "pack extensions are not available yet")
        existing = self._by_version(actor.tenant_id, parsed.metadata.id, parsed.metadata.version)
        if existing is not None and existing.get("status") == "installed":
            body = self._out(existing)
            body["import_results"] = []
            return body
        imported = import_bundle(
            self.store,
            actor,
            {
                "apiVersion": "agentic-runtime.dev/v1",
                "kind": "Bundle",
                "spec": {"resources": parsed.spec.resources},
            },
            dry_run=False,
        )
        now = utcnow()
        row_id = new_id()
        row = {
            "id": row_id,
            "tenant_id": actor.tenant_id,
            "pack_id": parsed.metadata.id,
            "version": parsed.metadata.version,
            "status": "installed",
            "manifest": manifest,
            "manifest_hash": digest_hex,
            "signature": signature,
            "signature_key_id": used_key,
            "installed_by": actor.user_id,
            "installed_at": now,
        }
        self.store.packs[row_id] = row
        for item in _result_rows(imported):
            if not isinstance(item, dict) or item.get("action") not in {
                "create",
                "new_version",
                "unchanged",
            }:
                continue
            resource_id = item.get("id")
            if not isinstance(resource_id, str):
                continue
            link_id = new_id()
            self.store.pack_resources[link_id] = {
                "id": link_id,
                "tenant_id": actor.tenant_id,
                "pack_row_id": row_id,
                "kind": item.get("kind"),
                "slug": item.get("key"),
                "resource_id": uuid.UUID(resource_id),
                "created_at": now,
            }
        _audit(
            self.store,
            actor,
            "pack.installed",
            parsed.metadata.id,
            {"version": parsed.metadata.version},
        )
        self.store.domain_events.append(
            {
                "topic": "pack.installed",
                "payload": {"pack_id": parsed.metadata.id, "version": parsed.metadata.version},
            }
        )
        body = self._out(row)
        body["import_results"] = imported["results"]
        return body

    def upgrade(
        self,
        actor: Actor,
        pack_id: str,
        manifest: dict[str, object],
        *,
        signature: str | None,
        key_id: str | None,
        accept_conflicts: bool,
    ) -> dict[str, object]:
        if not actor.has("packs:manage") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission packs:manage")
        current = self._current(actor, pack_id)
        parsed = self._parsed(manifest)
        if parsed.metadata.id != pack_id:
            raise ArError(ErrorCode.VALIDATION_FAILED, "manifest id does not match the pack")
        self._check_signature(actor, manifest, signature, key_id)
        if parsed.spec.extension is not None:
            raise ArError(ErrorCode.EXTENSION_UNAVAILABLE, "pack extensions are not available yet")
        if _semver(parsed.metadata.version) <= _semver(str(current["version"])):
            raise ArError(ErrorCode.INVALID_STATE, "upgrade version must be strictly greater")
        preview = import_bundle(
            self.store,
            actor,
            {"spec": {"resources": parsed.spec.resources}},
            dry_run=True,
        )
        conflicts = [
            item
            for item in _result_rows(preview)
            if isinstance(item, dict) and item.get("action") == "conflict"
        ]
        if conflicts and not accept_conflicts:
            return {
                "pack_id": pack_id,
                "version": parsed.metadata.version,
                "results": preview["results"],
            }
        if conflicts and accept_conflicts:
            for agent in self.store.agents.values():
                if agent.get("tenant_id") == actor.tenant_id:
                    agent["dirty"] = False
        installed = self.install(actor, manifest, signature=signature, key_id=key_id)
        _audit(self.store, actor, "pack.upgraded", pack_id, {"version": parsed.metadata.version})
        current["status"] = "uninstalled"
        return installed

    def uninstall(self, actor: Actor, pack_id: str, *, drop_schema: bool) -> dict[str, object]:
        if not actor.has("packs:manage") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission packs:manage")
        if drop_schema:
            raise ArError(
                ErrorCode.EXTENSION_UNAVAILABLE, "dropping a pack schema is not available yet"
            )
        row = self._current(actor, pack_id)
        row["status"] = "uninstalled"
        _audit(self.store, actor, "pack.uninstalled", pack_id, {"version": row.get("version")})
        return self._out(row)

    def _current(self, actor: Actor, pack_id: str) -> dict[str, object]:
        rows = [
            row
            for row in self.store.packs.values()
            if row.get("tenant_id") == actor.tenant_id
            and row.get("pack_id") == pack_id
            and row.get("status") == "installed"
        ]
        if not rows:
            raise NotFoundError()
        return cast("dict[str, object]", rows[-1])

    def _by_version(
        self, tenant_id: uuid.UUID, pack_id: str, version: str
    ) -> dict[str, object] | None:
        for row in self.store.packs.values():
            if (
                row.get("tenant_id") == tenant_id
                and row.get("pack_id") == pack_id
                and row.get("version") == version
            ):
                return cast("dict[str, object]", row)
        return None

    def _out(self, row: dict[str, object]) -> dict[str, object]:
        installed = row.get("installed_at")
        return {
            "id": str(row.get("id")),
            "pack_id": row.get("pack_id"),
            "version": row.get("version"),
            "status": row.get("status"),
            "installed_at": installed.isoformat() if hasattr(installed, "isoformat") else installed,
            "manifest_hash": row.get("manifest_hash"),
            "signature_key_id": row.get("signature_key_id"),
        }
