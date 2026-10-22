"""Review queues, items and sign-off. Spec: docs/03-specs/09-policy-approvals.md §11."""

import hashlib
import uuid
from typing import TYPE_CHECKING, Any, cast

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.approvals.errors import StepUpRequiredError
from ar_domain.approvals.sod import SodBook
from ar_domain.audit.memory import remember
from ar_domain.policy.service import _settings
from ar_domain.rows import as_dict, as_int, as_list, as_uuid

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_SUBJECTS = frozenset(
    {
        "artifact",
        "file",
        "message",
        "evidence_item",
        "run_record",
        "agent_card",
        "binder",
        "pack_record",
    }
)
_BULK_LIMIT = 100


class ReviewBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_queues(self, actor: Actor) -> list[dict[str, object]]:
        return [
            _queue(row)
            for row in self.store.review_queues.values()
            if row.get("tenant_id") == actor.tenant_id
        ]

    def create_queue(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        levels = body.get("levels")
        if not isinstance(levels, list) or not levels:
            raise ValidationFailedError("a queue needs at least one level")
        slug = str(body.get("slug") or "")
        if any(
            row.get("tenant_id") == actor.tenant_id and row.get("slug") == slug
            for row in self.store.review_queues.values()
        ):
            raise ConflictError("a queue with that slug already exists")
        subject = str(body.get("subject_type") or "")
        if subject not in _SUBJECTS:
            raise ValidationFailedError("subject_type is not supported")
        row = {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "slug": slug,
            "name": str(body.get("name") or slug),
            "subject_type": subject,
            "levels": levels,
            "statement_template": str(
                body.get("statement_template") or "I reviewed {title} ({content_hash})."
            ),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        self.store.review_queues[row["id"]] = row
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="review_queue.created",
            target_type="review_queue",
            target_id=row["id"],
            detail={"slug": slug},
        )
        return _queue(row)

    def get_queue(self, actor: Actor, queue_id: uuid.UUID) -> dict[str, object]:
        return _queue(self._queue(actor, queue_id))

    def patch_queue(
        self, actor: Actor, queue_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._queue(actor, queue_id)
        if body.get("name"):
            row["name"] = str(body["name"])
        if isinstance(body.get("levels"), list):
            row["levels"] = body["levels"]
        if "statement_template" in body:
            row["statement_template"] = str(body["statement_template"])
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="review_queue.updated",
            target_type="review_queue",
            target_id=queue_id,
            detail={},
        )
        return _queue(row)

    def delete_queue(self, actor: Actor, queue_id: uuid.UUID) -> None:
        row = self._queue(actor, queue_id)
        open_items = [
            item
            for item in self.store.review_items.values()
            if item.get("queue_id") == queue_id and item.get("status") in {"pending", "in_review"}
        ]
        if open_items:
            raise ConflictError("the queue still has open items")
        del self.store.review_queues[queue_id]
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="review_queue.deleted",
            target_type="review_queue",
            target_id=row["id"],
            detail={},
        )

    def list_items(
        self, actor: Actor, *, scope: str, status: str | None, queue_id: uuid.UUID | None
    ) -> list[dict[str, object]]:
        if scope == "all" and "reviews:read" not in actor.permissions:
            raise ForbiddenError()
        rows = []
        for row in self.store.review_items.values():
            if row.get("tenant_id") != actor.tenant_id:
                continue
            if status and row.get("status") != status:
                continue
            if queue_id is not None and row.get("queue_id") != queue_id:
                continue
            if scope == "prepared" and row.get("preparer_principal_id") != actor.user_id:
                continue
            if scope == "to_decide" and not self._eligible(actor, row):
                continue
            rows.append(self._summary(row))
        return rows

    def open_item(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        queue = self._queue(actor, _as_uuid(body.get("queue_id")))
        subject_type = str(body.get("subject_type") or queue["subject_type"])
        subject_id = _as_uuid(body.get("subject_id"))
        digest = _hash_subject(self.store, subject_type, subject_id, body.get("subject_ref"))
        if str(body.get("content_hash") or "") != digest:
            raise ValidationFailedError("hash_mismatch")
        statement = str(body.get("statement_text") or "")
        self._supersede_open(actor, subject_type, subject_id, digest)
        row = {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "queue_id": queue["id"],
            "subject_type": subject_type,
            "subject_id": subject_id,
            "subject_ref": body.get("subject_ref")
            if isinstance(body.get("subject_ref"), dict)
            else {},
            "content_hash": digest,
            "statement_text": statement,
            "statement_hash": hashlib.sha256(statement.encode()).hexdigest(),
            "status": "pending",
            "current_level": 1,
            "levels": as_list(queue.get("levels")),
            "preparer_principal_type": "user",
            "preparer_principal_id": actor.user_id,
            "agent_id": _agent_of(self.store, subject_type, subject_id),
            "expires_at": None,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        self.store.review_items[row["id"]] = row
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="review_item.created",
            target_type="review_item",
            target_id=row["id"],
            detail={"content_hash": digest},
        )
        self.store.domain_events.append(
            {
                "topic": "review_item.requested",
                "payload": {
                    "review_item_id": str(row["id"]),
                    "queue_id": str(queue["id"]),
                    "level": 1,
                },
                "at": utcnow().isoformat(),
            }
        )
        return self._detail(row)

    def get_item(self, actor: Actor, item_id: uuid.UUID) -> dict[str, object]:
        row = self._item(actor, item_id)
        if not self._can_see(actor, row):
            raise NotFoundError("review item not found")
        return self._detail(row)

    def decide(
        self, actor: Actor, item_id: uuid.UUID, body: dict[str, object], *, stepped_up: bool
    ) -> dict[str, object]:
        row = self._item(actor, item_id)
        if not self._eligible(actor, row):
            raise ForbiddenError("you cannot sign this item")
        if "reviews:decide" not in actor.permissions:
            raise ForbiddenError()
        choice = str(body.get("decision") or "")
        if choice not in {"approve", "reject", "delegate"}:
            raise ValidationFailedError("decision is invalid")
        self._hashes(row, body)
        level = self._level(row)
        needs_step = bool(level.get("step_up")) or self._final_step(row, level)
        if needs_step and actor.auth_method == "api_key":
            raise StepUpRequiredError()
        if needs_step and not stepped_up:
            raise StepUpRequiredError()
        SodBook(self.store).assert_signoff(actor, row, decision=choice)
        if choice == "delegate":
            return self._delegate(actor, row, body, level)
        self._sign(actor, row, choice, str(body.get("comment") or ""), level, stepped_up)
        if choice == "reject":
            row["status"] = "rejected"
        elif self._level_complete(row, level):
            levels = as_list(row.get("levels"))
            if as_int(row.get("current_level")) >= len(levels):
                row["status"] = "signed"
            else:
                row["current_level"] = as_int(row.get("current_level")) + 1
                row["status"] = "in_review"
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="review_item.decided",
            target_type="review_item",
            target_id=row["id"],
            detail={"status": row["status"], "level": level.get("level")},
        )
        self.store.domain_events.append(
            {
                "topic": "review_item.decided",
                "payload": {
                    "review_item_id": str(row["id"]),
                    "status": row["status"],
                    "level": row["current_level"],
                },
                "at": utcnow().isoformat(),
            }
        )
        return self._detail(row)

    def bulk(self, actor: Actor, body: dict[str, object], *, stepped_up: bool) -> dict[str, object]:
        items = body.get("items")
        if not isinstance(items, list) or len(items) > _BULK_LIMIT:
            raise ValidationFailedError("bulk decide accepts at most 100 items")
        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = _as_uuid(item.get("review_item_id"))
            try:
                self.decide(
                    actor,
                    item_id,
                    {
                        "decision": body.get("decision"),
                        "comment": body.get("comment"),
                        "content_hash": item.get("content_hash"),
                        "statement_hash": item.get("statement_hash"),
                    },
                    stepped_up=stepped_up,
                )
                results.append({"id": str(item_id), "status": "ok"})
            except Exception as exc:  # noqa: BLE001 — one item must not fail the batch
                results.append({"id": str(item_id), "status": "error", "error": str(exc)})
        return {"results": results}

    def _delegate(
        self,
        actor: Actor,
        row: dict[str, object],
        body: dict[str, object],
        level: dict[str, object],
    ) -> dict[str, object]:
        target = _as_uuid(body.get("delegated_to_user_id"))
        roles = set(self.store.user_roles.get(target, set()))
        if "reviews:decide" not in _permissions_for(roles):
            raise ValidationFailedError("the delegate cannot decide reviews")
        self._sign(actor, row, "delegate", str(body.get("comment") or ""), level, True, target)
        delegates = as_dict(row.get("delegates"))
        delegates[str(level.get("level"))] = str(target)
        row["delegates"] = delegates
        row["updated_at"] = utcnow()
        return self._detail(row)

    def _sign(  # noqa: PLR0917
        self,
        actor: Actor,
        row: dict[str, object],
        choice: str,
        comment: str,
        level: dict[str, object],
        stepped_up: bool,  # noqa: FBT001
        delegated: uuid.UUID | None = None,
    ) -> None:
        signoff_id = new_id()
        self.store.signoffs[signoff_id] = {
            "id": signoff_id,
            "tenant_id": actor.tenant_id,
            "review_item_id": row["id"],
            "level": as_int(level.get("level") or row.get("current_level"), 1),
            "decision": choice,
            "signer_principal_type": "user",
            "signer_principal_id": actor.user_id,
            "signer_role_key": level.get("role_key"),
            "content_hash": row["content_hash"],
            "statement_hash": row["statement_hash"],
            "comment": comment,
            "step_up_at": utcnow() if stepped_up else None,
            "delegated_to_user_id": delegated,
            "created_at": utcnow(),
        }
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="signoff.recorded",
            target_type="signoff",
            target_id=row["id"],
            detail={"decision": choice},
        )

    def _hashes(self, row: dict[str, object], body: dict[str, object]) -> None:
        current = _hash_subject(
            self.store,
            str(row["subject_type"]),
            as_uuid(row.get("subject_id")),
            row.get("subject_ref"),
        )
        if current != row["content_hash"]:
            row["status"] = "superseded"
            row["updated_at"] = utcnow()
            remember(
                self.store,
                tenant_id=row["tenant_id"],
                actor_id="system",
                action="review_item.superseded",
                target_type="review_item",
                target_id=row["id"],
                detail={},
            )
            raise ConflictError("content_changed")
        if str(body.get("content_hash") or "") != row["content_hash"]:
            raise ConflictError("content_changed")
        if str(body.get("statement_hash") or "") != row["statement_hash"]:
            raise ConflictError("content_changed")

    def _supersede_open(
        self, actor: Actor, subject_type: str, subject_id: uuid.UUID, digest: str
    ) -> None:
        for row in self.store.review_items.values():
            if row.get("subject_type") != subject_type or row.get("subject_id") != subject_id:
                continue
            if row.get("status") not in {"pending", "in_review"}:
                continue
            if row.get("content_hash") != digest:
                row["status"] = "superseded"
                remember(
                    self.store,
                    tenant_id=actor.tenant_id,
                    actor_id=actor.user_id,
                    action="review_item.superseded",
                    target_type="review_item",
                    target_id=row["id"],
                    detail={},
                )

    def _eligible(self, actor: Actor, row: dict[str, object]) -> bool:
        if row.get("status") not in {"pending", "in_review"}:
            return False
        if str(row.get("preparer_principal_id")) == str(actor.user_id):
            return False
        level = self._level(row)
        delegated = row.get("delegates")
        if isinstance(delegated, dict) and delegated.get(str(level.get("level"))) == str(
            actor.user_id
        ):
            return True
        role_key = str(level.get("role_key") or "")
        if role_key and role_key not in actor.roles and "tenant_admin" not in actor.roles:
            return False
        return "reviews:decide" in actor.permissions

    def _can_see(self, actor: Actor, row: dict[str, object]) -> bool:
        if "reviews:read" in actor.permissions:
            return True
        if str(row.get("preparer_principal_id")) == str(actor.user_id):
            return True
        return self._eligible(actor, row)

    def _level(self, row: dict[str, object]) -> dict[str, object]:
        levels = as_list(row.get("levels"))
        current = as_int(row.get("current_level"), 1)
        for level in levels:
            if isinstance(level, dict) and as_int(level.get("level")) == current:
                return cast("dict[str, object]", level)
        return {"level": current, "required_count": 1, "step_up": False, "role_key": ""}

    def _level_complete(self, row: dict[str, object], level: dict[str, object]) -> bool:
        needed = as_int(level.get("required_count"), 1)
        current_level = as_int(level.get("level"))
        count = 0
        for sign in self.store.signoffs.values():
            if (
                sign.get("review_item_id") == row["id"]
                and as_int(sign.get("level")) == current_level
                and sign.get("decision") == "approve"
            ):
                count += 1
        return count >= needed

    def _final_step(self, row: dict[str, object], level: dict[str, object]) -> bool:
        levels = as_list(row.get("levels"))
        if as_int(level.get("level")) < len(levels):
            return False
        security = _settings(self.store, as_uuid(row.get("tenant_id"))).get("security")
        if isinstance(security, dict):
            return bool(security.get("require_step_up_for_signoff", True))
        return True

    def _queue(self, actor: Actor, queue_id: uuid.UUID) -> dict[str, object]:
        row = self.store.review_queues.get(queue_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("review queue not found")
        return row

    def _item(self, actor: Actor, item_id: uuid.UUID) -> dict[str, object]:
        row = self.store.review_items.get(item_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("review item not found")
        return row

    def _summary(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": row["id"],
            "queue_id": row["queue_id"],
            "subject_type": row["subject_type"],
            "subject_id": row["subject_id"],
            "status": row["status"],
            "current_level": row["current_level"],
            "content_hash": row["content_hash"],
            "created_at": row["created_at"],
        }

    def _detail(self, row: dict[str, object]) -> dict[str, object]:
        body = self._summary(row)
        body["statement_text"] = row["statement_text"]
        body["statement_hash"] = row["statement_hash"]
        body["preparer_principal_id"] = row["preparer_principal_id"]
        body["signoffs"] = [
            {
                "level": sign.get("level"),
                "decision": sign.get("decision"),
                "signer_principal_id": sign.get("signer_principal_id"),
                "comment": sign.get("comment"),
                "created_at": sign.get("created_at"),
            }
            for sign in self.store.signoffs.values()
            if sign.get("review_item_id") == row["id"]
        ]
        return body


def _queue(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row.get("id"),
        "slug": row.get("slug"),
        "name": row.get("name"),
        "subject_type": row.get("subject_type"),
        "levels": row.get("levels"),
        "statement_template": row.get("statement_template"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _hash_subject(store: Any, subject_type: str, subject_id: uuid.UUID, ref: object) -> str:
    if subject_type == "message":
        message = store.messages.get(subject_id)
        if not isinstance(message, dict):
            raise NotFoundError("subject not found")
        return hashlib.sha256(str(message.get("text") or "").encode()).hexdigest()
    if subject_type == "file":
        blob = store.blobs.get(subject_id, b"")
        return hashlib.sha256(blob).hexdigest()
    if subject_type == "pack_record" and isinstance(ref, dict) and ref.get("content_hash"):
        return str(ref["content_hash"])
    if subject_type in _SUBJECTS:
        extra = store.blobs.get(subject_id)
        if isinstance(extra, bytes) and extra:
            return hashlib.sha256(extra).hexdigest()
        return hashlib.sha256(f"{subject_type}:{subject_id}".encode()).hexdigest()
    raise ValidationFailedError("hash_mismatch")


def _agent_of(store: Any, subject_type: str, subject_id: uuid.UUID) -> uuid.UUID | None:
    if subject_type != "message":
        return None
    message = store.messages.get(subject_id)
    if not isinstance(message, dict):
        return None
    run = store.runs.get(message.get("run_id"))
    agent_id = run.get("agent_id") if isinstance(run, dict) else None
    if isinstance(agent_id, uuid.UUID):
        return agent_id
    return None


def _as_uuid(value: object) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError("id is required") from exc


def _permissions_for(roles: set[str]) -> set[str]:
    from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS  # noqa: PLC0415

    found: set[str] = set()
    for role in roles:
        found.update(SYSTEM_ROLE_PERMISSIONS.get(role, ()))
    return found
