"""Legal hold, retention and erasure. Spec: docs/03-specs/21-records-governance.md §2."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode, ForbiddenError, NotFoundError
from ar_common.ids import new_id
from ar_common.jcs import canonical_json
from ar_common.time import utcnow
from ar_domain.identity.service import assert_step_up
from ar_domain.records.access import audit, missing, own, public, require
from ar_domain.records.memory import blobs, bucket

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_MINIMUM = frozenset({"evidence_item", "run_record", "signoff", "audit_archive", "cert_in_log"})
_FLOOR_DAYS = 180
_DEFAULTS: tuple[tuple[str, int, str], ...] = (
    ("conversation", 365, "delete"),
    ("run", 365, "delete"),
    ("run_record", 2555, "archive_then_delete"),
    ("evidence_item", 2555, "archive_then_delete"),
    ("file", 365, "delete"),
    ("memory_fact", 730, "delete"),
    ("signoff", 2555, "archive_then_delete"),
    ("agent_card", 2555, "archive_then_delete"),
    ("cert_in_log", 180, "delete"),
    ("audit_archive", 2555, "keep"),
    ("guest_grant", 365, "delete"),
)


class HoldBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_holds(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "holds:manage")
        rows = [
            self._out(row)
            for row in bucket(self.store, "holds").values()
            if own(row, actor.tenant_id)
        ]
        rows.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        return rows

    def officers(self, actor: Actor) -> list[dict[str, str]]:
        require(actor, "holds:manage")
        found = []
        roles = getattr(self.store, "user_roles", {})
        names = getattr(self.store, "display_names", {})
        if isinstance(roles, dict):
            for user_id, granted in roles.items():
                if "tenant_admin" in granted or "holds:manage" in granted:
                    found.append(
                        {
                            "id": str(user_id),
                            "display_name": str(names.get(user_id, "Officer"))
                            if isinstance(names, dict)
                            else "Officer",
                        }
                    )
        return found

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        require(actor, "holds:manage")
        self._step_up(actor)
        approver = _uuid(body.get("approver_user_id"))
        if approver == actor.user_id:
            raise ForbiddenError("the approver must be a different person")
        if not self._officer(approver):
            raise ForbiddenError("approver lacks holds:manage")
        raw_scope = body.get("scope_query")
        scope: dict[str, object] = raw_scope if isinstance(raw_scope, dict) else {}
        hold_id = new_id()
        now = utcnow()
        row = {
            "id": hold_id,
            "tenant_id": actor.tenant_id,
            "matter": str(body.get("matter") or ""),
            "custodians": body.get("custodians")
            if isinstance(body.get("custodians"), list)
            else [],
            "scope_query": scope,
            "status": "active",
            "approver_user_id": approver,
            "created_by": actor.user_id,
            "started_at": now,
            "released_at": None,
            "release_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        members = self._members(actor, hold_id, scope)
        bucket(self.store, "holds")[hold_id] = row
        audit(
            self.store,
            actor,
            "legal_hold.created",
            "legal_hold",
            hold_id,
            {"matter": row["matter"], "member_count": len(members)},
        )
        body_out = self._out(row)
        body_out["member_count"] = len(members)
        return body_out

    def get(self, actor: Actor, hold_id: uuid.UUID) -> dict[str, object]:
        require(actor, "holds:manage")
        row = self._row(actor, hold_id)
        body = self._out(row)
        body["members"] = [
            public(member)
            for member in bucket(self.store, "hold_members").values()
            if member.get("hold_id") == hold_id and own(member, actor.tenant_id)
        ]
        return body

    def release(self, actor: Actor, hold_id: uuid.UUID, reason: str) -> dict[str, object]:
        require(actor, "holds:manage")
        self._step_up(actor)
        row = self._row(actor, hold_id)
        if row.get("created_by") == actor.user_id:
            raise ForbiddenError("the creator cannot release this hold")
        if row.get("status") != "active":
            raise ArError(ErrorCode.INVALID_STATE, "hold is not active")
        row["status"] = "released"
        row["released_at"] = utcnow()
        row["release_reason"] = reason
        self._restore(actor, hold_id)
        audit(self.store, actor, "legal_hold.released", "legal_hold", hold_id, {"reason": reason})
        return self._out(row)

    def put_schedule(
        self, actor: Actor, record_class: str, body: dict[str, object]
    ) -> dict[str, object]:
        require(actor, "retention:manage")
        days = int(str(body.get("retention_days") or 0))
        disposition = str(body.get("disposition") or "delete")
        if record_class in _MINIMUM and days < _FLOOR_DAYS:
            raise ArError(ErrorCode.RETENTION_BELOW_MINIMUM, "retention_below_minimum")
        if days < 1:
            raise ArError(ErrorCode.VALIDATION_FAILED, "retention_days must be at least 1")
        if disposition not in {"delete", "archive_then_delete", "keep"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "disposition is invalid")
        self.ensure_defaults(actor.tenant_id)
        key = (str(actor.tenant_id), record_class)
        current = bucket(self.store, "schedules").get(key)
        if not isinstance(current, dict):
            current = {
                "id": new_id(),
                "tenant_id": actor.tenant_id,
                "record_class": record_class,
                "created_at": utcnow(),
            }
            bucket(self.store, "schedules")[key] = current
        current["retention_days"] = days
        current["disposition"] = disposition
        current["updated_at"] = utcnow()
        audit(
            self.store,
            actor,
            "retention_schedule.updated",
            "retention_schedule",
            current["id"],
            {"record_class": record_class, "retention_days": days, "disposition": disposition},
        )
        return _schedule_out(current)

    def list_schedules(self, actor: Actor) -> list[dict[str, object]]:
        if not actor.has("retention:manage") and not actor.has("audit:read"):
            raise ForbiddenError("missing permission retention:manage")
        self.ensure_defaults(actor.tenant_id)
        rows = [
            _schedule_out(row)
            for row in bucket(self.store, "schedules").values()
            if own(row, actor.tenant_id)
        ]
        rows.sort(key=lambda item: str(item.get("record_class")))
        return rows

    def ensure_defaults(self, tenant_id: uuid.UUID) -> None:
        for record_class, days, disposition in _DEFAULTS:
            key = (str(tenant_id), record_class)
            if key in bucket(self.store, "schedules"):
                continue
            bucket(self.store, "schedules")[key] = {
                "id": new_id(),
                "tenant_id": tenant_id,
                "record_class": record_class,
                "retention_days": days,
                "disposition": disposition,
                "created_at": utcnow(),
                "updated_at": utcnow(),
            }

    def sweep(self, actor: Actor, *, now: datetime | None = None) -> dict[str, object]:
        moment = now or utcnow()
        self.ensure_defaults(actor.tenant_id)
        disposed: list[str] = []
        held: list[str] = []
        for schedule in list(bucket(self.store, "schedules").values()):
            if not own(schedule, actor.tenant_id):
                continue
            record_class = str(schedule.get("record_class"))
            days = int(str(schedule.get("retention_days") or 0))
            for record_id, row in list(_class_rows(self.store, record_class, actor.tenant_id)):
                created = row.get("created_at") or row.get("sealed_at") or row.get("collected_at")
                if not isinstance(created, datetime) or created + timedelta(days=days) > moment:
                    continue
                if is_held(self.store, record_class, record_id):
                    held.append(str(record_id))
                    continue
                self._dispose(actor, record_class, record_id, row, str(schedule.get("disposition")))
                disposed.append(str(record_id))
        audit(
            self.store,
            actor,
            "retention.swept",
            "tenant",
            actor.tenant_id,
            {"disposed": len(disposed), "held": len(held)},
        )
        return {"disposed": disposed, "held_record_ids": held}

    def erase(self, actor: Actor, user_id: uuid.UUID) -> dict[str, object]:
        require(actor, "users:manage")
        held: list[str] = []
        removed = 0
        for record_class, source in (
            ("conversation", self.store.conversations),
            ("file", self.store.files),
            ("memory_fact", self.store.memory_facts),
        ):
            for record_id, row in list(source.items()):
                if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
                    continue
                owner = row.get("user_id") or row.get("owner_user_id") or row.get("uploaded_by")
                if owner != user_id:
                    continue
                if is_held(self.store, record_class, record_id):
                    held.append(str(record_id))
                    continue
                source.pop(record_id, None)
                if record_class == "conversation":
                    _drop_children(self.store, record_id)
                if record_class == "file":
                    self.store.blobs.pop(record_id, None)
                removed += 1
        _drop_user_edges(self.store, actor.tenant_id, user_id, held)
        detail = {"user_id": str(user_id), "removed": removed, "held_record_ids": held}
        audit(self.store, actor, "erasure.completed", "user", user_id, detail)
        return detail

    def certificates(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "audit:read")
        rows = [
            public(row)
            for row in bucket(self.store, "certificates").values()
            if own(row, actor.tenant_id)
        ]
        rows.sort(key=lambda item: str(item.get("disposed_at") or ""), reverse=True)
        return rows

    def _dispose(
        self,
        actor: Actor,
        record_class: str,
        record_id: object,
        row: dict[str, object],
        method: str,
    ) -> None:
        if method == "keep":
            return
        raw = canonical_json({"id": str(record_id), "class": record_class})
        digest = hashlib.sha256(raw).hexdigest()
        if method == "archive_then_delete":
            key = f"retention/{actor.tenant_id}/{record_class}/{record_id}"
            blobs(self.store, "archive")[key] = raw
        cert_body = {
            "record_class": record_class,
            "record_id": str(record_id),
            "content_sha256": digest,
            "method": method,
            "disposed_at": utcnow().isoformat(),
        }
        cert_hash = hashlib.sha256(canonical_json(cert_body)).hexdigest()  # type: ignore[arg-type]
        cert_id = new_id()
        bucket(self.store, "certificates")[cert_id] = {
            "id": cert_id,
            "tenant_id": actor.tenant_id,
            "record_class": record_class,
            "record_id": record_id,
            "content_sha256": digest,
            "method": method,
            "disposed_at": utcnow(),
            "certificate_hash": cert_hash,
            "actor_user_id": actor.user_id,
        }
        if record_class == "evidence_item" and isinstance(record_id, uuid.UUID):
            row["status"] = "disposed"
            audit(
                self.store,
                actor,
                "evidence.disposed",
                "evidence_item",
                record_id,
                {"method": method},
            )
        audit(
            self.store,
            actor,
            "disposition.certified",
            record_class,
            record_id,
            {"certificate_hash": cert_hash},
        )

    def _members(self, actor: Actor, hold_id: uuid.UUID, scope: dict[str, object]) -> list[object]:
        classes = scope.get("record_classes")
        wanted = set(classes) if isinstance(classes, list) else set()
        explicit = scope.get("conversation_ids")
        ids = {str(item) for item in explicit} if isinstance(explicit, list) else set()
        evidence_ids = scope.get("evidence_ids")
        evidence = {str(item) for item in evidence_ids} if isinstance(evidence_ids, list) else set()
        created: list[object] = []
        if ids or "conversation" in wanted:
            for row in self.store.conversations.values():
                if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
                    continue
                if ids and str(row.get("id")) not in ids:
                    continue
                if not ids and "conversation" not in wanted:
                    continue
                created.append(self._member(actor, hold_id, "conversation", row))
        if evidence or "evidence_item" in wanted:
            for row in bucket(self.store, "evidence").values():
                if not own(row, actor.tenant_id):
                    continue
                if evidence and str(row.get("id")) not in evidence:
                    continue
                created.append(self._member(actor, hold_id, "evidence_item", row))
        return created

    def _member(
        self, actor: Actor, hold_id: uuid.UUID, record_class: str, row: dict[str, object]
    ) -> object:
        record_id = row.get("id")
        previous = str(row.get("retention_class") or "")
        if record_class == "conversation":
            row["retention_class"] = "legal_hold"
        if record_class == "evidence_item":
            row["legal_hold"] = True
        key = (str(hold_id), record_class, str(record_id))
        bucket(self.store, "hold_members")[key] = {
            "tenant_id": actor.tenant_id,
            "hold_id": hold_id,
            "record_class": record_class,
            "record_id": record_id,
            "detail": {"previous_retention_class": previous},
            "applied_at": utcnow(),
        }
        return record_id

    def _restore(self, _actor: Actor, hold_id: uuid.UUID) -> None:
        for _key, member in list(bucket(self.store, "hold_members").items()):
            if member.get("hold_id") != hold_id:
                continue
            record_id = member.get("record_id")
            covered = (
                member.get("record_class") == "conversation"
                and isinstance(record_id, uuid.UUID)
                and not _covered_elsewhere(self.store, hold_id, record_id)
            )
            if covered:
                row = self.store.conversations.get(record_id)
                detail = member.get("detail")
                previous = (
                    detail.get("previous_retention_class") if isinstance(detail, dict) else ""
                )
                if isinstance(row, dict):
                    row["retention_class"] = previous or "conversation"
            if member.get("record_class") == "evidence_item" and isinstance(record_id, uuid.UUID):
                row = bucket(self.store, "evidence").get(record_id)
                if isinstance(row, dict) and not _covered_elsewhere(self.store, hold_id, record_id):
                    row["legal_hold"] = False

    def _row(self, actor: Actor, hold_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "holds").get(hold_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            missing()
        return row

    def _officer(self, user_id: uuid.UUID) -> bool:
        roles = getattr(self.store, "user_roles", {})
        granted = roles.get(user_id) if isinstance(roles, dict) else None
        if isinstance(granted, set | frozenset):
            return "tenant_admin" in granted or "holds:manage" in granted
        return False

    def _step_up(self, actor: Actor) -> None:
        assert_step_up(actor.step_up_at, now=utcnow(), ttl_s=600, required=True)

    def _out(self, row: dict[str, object]) -> dict[str, object]:
        body = public(row)
        approver = body.get("approver_user_id")
        names = getattr(self.store, "display_names", {})
        label = names.get(approver, "") if isinstance(names, dict) else ""
        body["approver"] = {"id": approver, "display_name": label}
        return body


def is_held(store: Any, record_class: str, record_id: object) -> bool:
    for member in bucket(store, "hold_members").values():
        if member.get("record_class") == record_class and member.get("record_id") == record_id:
            hold = bucket(store, "holds").get(member.get("hold_id"))
            if isinstance(hold, dict) and hold.get("status") == "active":
                return True
    return False


def _covered_elsewhere(store: Any, hold_id: uuid.UUID, record_id: uuid.UUID) -> bool:
    for member in bucket(store, "hold_members").values():
        if member.get("hold_id") == hold_id or member.get("record_id") != record_id:
            continue
        hold = bucket(store, "holds").get(member.get("hold_id"))
        if isinstance(hold, dict) and hold.get("status") == "active":
            return True
    return False


def _class_rows(
    store: Any, record_class: str, tenant_id: uuid.UUID
) -> list[tuple[object, dict[str, object]]]:
    source: Any
    if record_class == "conversation":
        source = store.conversations
    elif record_class == "evidence_item":
        source = bucket(store, "evidence")
    elif record_class == "file":
        source = store.files
    else:
        source = {}
    found = []
    for record_id, row in source.items():
        if isinstance(row, dict) and row.get("tenant_id") == tenant_id:
            found.append((record_id, row))
    return found


def _drop_children(store: Any, conversation_id: object) -> None:
    for message_id, message in list(store.messages.items()):
        if isinstance(message, dict) and message.get("conversation_id") == conversation_id:
            store.messages.pop(message_id, None)
    for run_id, run in list(store.runs.items()):
        if isinstance(run, dict) and run.get("conversation_id") == conversation_id:
            store.runs.pop(run_id, None)


def _drop_user_edges(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, held: list[str]) -> None:
    grants = getattr(store, "credential_grants", {})
    if isinstance(grants, dict):
        for grant_id, row in list(grants.items()):
            if isinstance(row, dict) and row.get("user_id") == user_id:
                grants.pop(grant_id, None)
    identities = getattr(store, "channel_identities", {})
    if isinstance(identities, dict):
        for identity_id, row in list(identities.items()):
            if (
                isinstance(row, dict)
                and row.get("user_id") == user_id
                and row.get("tenant_id") == tenant_id
            ):
                identities.pop(identity_id, None)
    points = bucket(store, "retrieval_points")
    for point_id, row in list(points.items()):
        if isinstance(row, dict) and row.get("user_id") == user_id:
            if row.get("held"):
                held.append(str(point_id))
                continue
            points.pop(point_id, None)


def _schedule_out(row: dict[str, object]) -> dict[str, object]:
    body = public(row)
    days = int(str(body.get("retention_days") or 0))
    record_class = str(body.get("record_class") or "")
    body["effective_days"] = max(days, _FLOOR_DAYS) if record_class in _MINIMUM else days
    return body


def _uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        return uuid.UUID(value)
    raise NotFoundError()


def certificate_hash(body: dict[str, JsonValue]) -> str:
    return hashlib.sha256(canonical_json(body)).hexdigest()
