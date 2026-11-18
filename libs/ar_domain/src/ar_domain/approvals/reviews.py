"""Review queues, items and sign-off. Spec: docs/03-specs/09-policy-approvals.md §11."""

import hashlib
import uuid
from typing import TYPE_CHECKING, Any, cast

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.approvals.errors import StepUpRequiredError
from ar_domain.approvals.models import REVIEW_SUBJECTS
from ar_domain.approvals.sod import SodBook
from ar_domain.audit.memory import remember
from ar_domain.policy.service import _settings
from ar_domain.rows import as_dict, as_int, as_list, as_uuid

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_SUBJECTS = REVIEW_SUBJECTS
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
        from ar_domain.approvals.reply_review import reply_queue_id  # noqa: PLC0415

        if reply_queue_id(self.store, actor.tenant_id) == queue_id:
            raise ConflictError(
                "This queue is where accepted replies are signed. "
                "Choose another queue for reply acceptance first."
            )
        from ar_domain.spreadsheet.saved import SETTING as SAVED_QUERY_SETTING  # noqa: PLC0415

        chosen = _settings(self.store, actor.tenant_id).get("approvals")
        if isinstance(chosen, dict) and str(chosen.get(SAVED_QUERY_SETTING) or "") == str(queue_id):
            raise ConflictError(
                "This queue is where saved queries are signed off. "
                "Choose another queue for saved queries first."
            )
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
        row = self.draft(
            actor,
            queue,
            subject_type=subject_type,
            subject_id=subject_id,
            subject_ref=body.get("subject_ref"),
            statement=str(body.get("statement_text") or ""),
            preparer=("user", actor.user_id),
        )
        return self.file(actor, row)

    def draft(
        self,
        actor: Actor,
        queue: dict[str, object],
        *,
        subject_type: str,
        subject_id: uuid.UUID,
        subject_ref: object,
        statement: str,
        preparer: tuple[str, uuid.UUID],
    ) -> dict[str, object]:
        """A review item that is not stored yet, so a caller can check it before filing it.

        ``preparer`` is who made the subject: the person who opened the item, or the agent
        that wrote a reply. The preparer can never sign the item.
        """
        return {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "queue_id": queue["id"],
            "subject_type": subject_type,
            "subject_id": subject_id,
            "subject_ref": subject_ref if isinstance(subject_ref, dict) else {},
            "content_hash": _hash_subject(self.store, subject_type, subject_id, subject_ref),
            "statement_text": statement,
            "statement_hash": hashlib.sha256(statement.encode()).hexdigest(),
            "status": "pending",
            "current_level": 1,
            "levels": as_list(queue.get("levels")),
            "preparer_principal_type": preparer[0],
            "preparer_principal_id": preparer[1],
            "agent_id": _agent_of(self.store, subject_type, subject_id),
            "expires_at": None,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }

    def file(self, actor: Actor, row: dict[str, object]) -> dict[str, object]:
        """Store a drafted item, retiring open items for older content of the same subject."""
        digest = str(row["content_hash"])
        self._supersede_open(
            actor, str(row["subject_type"]), as_uuid(row.get("subject_id")), digest
        )
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
                    "queue_id": str(row["queue_id"]),
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
        self.assert_may_sign(actor, row)
        choice = str(body.get("decision") or "")
        if choice not in {"approve", "reject", "delegate"}:
            raise ValidationFailedError("decision is invalid")
        self._hashes(row, body)
        level = self._level(row)
        self.assert_cleared(actor, row, choice, stepped_up=stepped_up)
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

    def assert_may_sign(self, actor: Actor, row: dict[str, object]) -> None:
        """The caller is eligible at the item's current level and may decide reviews."""
        if not self._eligible(actor, row):
            raise ForbiddenError("you cannot sign this item")
        if "reviews:decide" not in actor.permissions:
            raise ForbiddenError()

    def needs_step_up(self, row: dict[str, object]) -> bool:
        """The item's current level asks the signer to confirm who they are first."""
        level = self._level(row)
        return bool(level.get("step_up")) or self._final_step(row, level)

    def assert_cleared(
        self, actor: Actor, row: dict[str, object], choice: str, *, stepped_up: bool
    ) -> None:
        """Step-up and segregation of duties, checked before any sign-off is written."""
        if self.needs_step_up(row) and (actor.auth_method == "api_key" or not stepped_up):
            raise StepUpRequiredError()
        SodBook(self.store).assert_signoff(actor, row, decision=choice)

    def may_sign(self, actor: Actor, row: dict[str, object]) -> bool:
        """Whether the caller could sign this item now, without recording anything."""
        return (
            "reviews:decide" in actor.permissions
            and self._eligible(actor, row)
            and not SodBook(self.store).signoff_violations(actor, row)
        )

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
        # What the signer is asked to read, when the subject carries its own text.
        body["subject_ref"] = as_dict(row.get("subject_ref"))
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
    if subject_type == "saved_query":
        from ar_domain.spreadsheet.saved import subject_hash  # noqa: PLC0415

        return subject_hash(store, subject_id)
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
