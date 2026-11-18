"""Saved table queries: named, versioned, and signed off before they run when asked.

A version is written once. Saving under a name that exists adds the next version. When
the tenant names a review queue in ``approvals.saved_query_review_queue_id``, each
version needs a signed review item before it may run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.jcs import args_hash
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.identity.tenant_settings import section, settings_for
from ar_domain.rows import as_int, as_list

if TYPE_CHECKING:
    from datetime import datetime

SUBJECT_TYPE = "saved_query"
SETTING = "saved_query_review_queue_id"
_NAME_MAX = 120
_OPEN = frozenset({"pending", "in_review"})


@dataclass(frozen=True, slots=True)
class SignOff:
    """Where one version stands. ``status`` is ``not_required``, ``unrequested`` or the item's."""

    required: bool
    status: str
    queue_name: str = ""
    role: str = ""
    review_item_id: uuid.UUID | None = None
    approvers: tuple[str, ...] = field(default=())
    approved_at: datetime | None = None

    @property
    def runnable(self) -> bool:
        return not self.required or self.status == "signed"


def content_hash(name: str, version: int, sql: str, description: str) -> str:
    """The digest a reviewer signs. Any change to the query gives a new one."""
    return args_hash({"name": name, "version": version, "sql": sql, "description": description})


def review_queue_id(store: Any, tenant_id: object) -> uuid.UUID | None:
    """The queue the tenant chose for saved queries, or None when it chose none."""
    raw = section(settings_for(store, tenant_id), "approvals").get(SETTING)
    if raw is None or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise ValidationFailedError(
            "The workspace setting for saved-query sign-off does not name a review queue. "
            "An administrator must choose a queue in Settings."
        ) from exc


class SavedQueryBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def versions(self, tenant_id: uuid.UUID, name: str) -> list[dict[str, object]]:
        """Every version saved under ``name``, oldest first. Names ignore case."""
        wanted = name.strip().casefold()
        rows = [
            row
            for row in self.store.saved_queries.values()
            if row.get("tenant_id") == tenant_id and str(row.get("name") or "").casefold() == wanted
        ]
        return sorted(rows, key=lambda row: as_int(row.get("version")))

    def latest(self, tenant_id: uuid.UUID) -> list[dict[str, object]]:
        """The newest version of each name, by name."""
        newest: dict[str, dict[str, object]] = {}
        for row in self.store.saved_queries.values():
            if row.get("tenant_id") != tenant_id:
                continue
            key = str(row.get("name") or "").casefold()
            held = newest.get(key)
            if held is None or as_int(row.get("version")) > as_int(held.get("version")):
                newest[key] = row
        return [newest[key] for key in sorted(newest)]

    def get(self, tenant_id: uuid.UUID, name: str, version: int | None) -> dict[str, object]:
        rows = self.versions(tenant_id, name)
        if not rows:
            raise NotFoundError(f"no saved query is named {name}")
        if version is None:
            return rows[-1]
        for row in rows:
            if as_int(row.get("version")) == version:
                return row
        raise NotFoundError(
            f"{rows[-1]['name']} has no version {version}. "
            f"Its versions are 1 to {as_int(rows[-1].get('version'))}."
        )

    def save(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, *, name: str, sql: str, description: str
    ) -> tuple[dict[str, object], bool]:
        """Store the next version, and ask for sign-off when the tenant requires it.

        Returns the version and whether it is new. Saving the same statement and
        description as the newest version adds nothing; it only asks for sign-off again
        when that version has no open or signed review item.
        """
        label = name.strip()
        statement = sql.strip()
        if not label or len(label) > _NAME_MAX:
            raise ValidationFailedError(f"name is required and at most {_NAME_MAX} characters")
        if not statement:
            raise ValidationFailedError("sql is required")
        queue = self._queue(tenant_id)
        held = self.versions(tenant_id, label)
        newest = held[-1] if held else None
        if (
            newest is not None
            and newest.get("sql") == statement
            and newest.get("description") == description
        ):
            if queue is not None and self._item(tenant_id, newest) is None:
                self._request(tenant_id, user_id, newest, queue)
            return newest, False
        version = as_int(newest.get("version")) + 1 if newest is not None else 1
        label = str(newest["name"]) if newest is not None else label
        row: dict[str, object] = {
            "id": new_id(),
            "tenant_id": tenant_id,
            "name": label,
            "version": version,
            "sql": statement,
            "description": description,
            "content_hash": content_hash(label, version, statement, description),
            "created_by_user_id": user_id,
            "created_at": utcnow(),
        }
        self.store.saved_queries[row["id"]] = row
        remember(
            self.store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="saved_query.saved",
            target_type="saved_query",
            target_id=row["id"],
            detail={"name": label, "version": version, "content_hash": row["content_hash"]},
        )
        if queue is not None:
            self._request(tenant_id, user_id, row, queue)
        return row, True

    def sign_off(self, tenant_id: uuid.UUID, row: dict[str, object]) -> SignOff:
        """Whether this version may run now, and who signed or must sign it."""
        queue = self._queue(tenant_id)
        if queue is None:
            return SignOff(required=False, status="not_required")
        levels = as_list(queue.get("levels"))
        first = levels[0] if levels and isinstance(levels[0], dict) else {}
        role = str(first.get("role_key") or first.get("role") or "")
        queue_name = str(queue.get("name") or queue.get("slug") or "")
        item = self._item(tenant_id, row)
        if item is None:
            return SignOff(required=True, status="unrequested", queue_name=queue_name, role=role)
        status = str(item.get("status") or "pending")
        if status == "signed" and item.get("content_hash") != _digest(row):
            # The stored version no longer matches what was signed. It does not run.
            status = "superseded"
        signs = [
            sign
            for sign in self.store.signoffs.values()
            if sign.get("review_item_id") == item["id"] and sign.get("decision") == "approve"
        ]
        names = getattr(self.store, "display_names", {})
        approvers = tuple(
            str(names.get(sign.get("signer_principal_id")) or sign.get("signer_principal_id"))
            for sign in signs
        )
        stamps = [sign["created_at"] for sign in signs if sign.get("created_at") is not None]
        return SignOff(
            required=True,
            status=status,
            queue_name=queue_name,
            role=role,
            review_item_id=item["id"] if isinstance(item["id"], uuid.UUID) else None,
            approvers=approvers if status == "signed" else (),
            approved_at=max(stamps) if stamps and status == "signed" else None,
        )

    def record_run(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, row: dict[str, object], *, rows: int
    ) -> None:
        remember(
            self.store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="saved_query.run",
            target_type="saved_query",
            target_id=row["id"],
            detail={
                "name": row.get("name"),
                "version": row.get("version"),
                "content_hash": row.get("content_hash"),
                "rows": rows,
            },
        )

    def _queue(self, tenant_id: uuid.UUID) -> dict[str, object] | None:
        queue_id = review_queue_id(self.store, tenant_id)
        if queue_id is None:
            return None
        queue = self.store.review_queues.get(queue_id)
        if not isinstance(queue, dict) or queue.get("tenant_id") != tenant_id:
            # Fail closed: a queue that was named and is gone must not turn sign-off off.
            raise ValidationFailedError(
                "The review queue chosen for saved-query sign-off no longer exists. "
                "An administrator must choose a queue in Settings."
            )
        return queue

    def _item(self, tenant_id: uuid.UUID, row: dict[str, object]) -> dict[str, object] | None:
        """The review item that decides this version: a signed one, else the newest live one."""
        found: list[dict[str, object]] = [
            item
            for item in self.store.review_items.values()
            if item.get("tenant_id") == tenant_id
            and item.get("subject_type") == SUBJECT_TYPE
            and item.get("subject_id") == row["id"]
        ]
        for wanted in ({"signed"}, _OPEN, {"rejected"}):
            matching = [item for item in found if item.get("status") in wanted]
            if matching:
                return max(matching, key=lambda item: str(item.get("created_at")))
        return None

    def _request(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        row: dict[str, object],
        queue: dict[str, object],
    ) -> None:
        from ar_domain.agents.access import Actor  # noqa: PLC0415
        from ar_domain.approvals.reviews import ReviewBook  # noqa: PLC0415

        digest = str(row["content_hash"])
        title = f"saved query {row['name']} version {row['version']}"
        template = str(queue.get("statement_template") or "I reviewed {title} ({content_hash}).")
        actor = Actor(tenant_id, user_id, frozenset({"reviews:read"}))
        item = ReviewBook(self.store).open_item(
            actor,
            {
                "queue_id": queue["id"],
                "subject_type": SUBJECT_TYPE,
                "subject_id": row["id"],
                "subject_ref": {
                    "name": row["name"],
                    "version": row["version"],
                    "sql": row["sql"],
                    "description": row["description"],
                    "content_hash": digest,
                },
                "content_hash": digest,
                "statement_text": template.replace("{title}", title).replace(
                    "{content_hash}", digest
                ),
            },
        )
        remember(
            self.store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="saved_query.signoff_requested",
            target_type="saved_query",
            target_id=row["id"],
            detail={
                "name": row["name"],
                "version": row["version"],
                "content_hash": digest,
                "review_item_id": str(item["id"]),
                "queue_id": str(queue["id"]),
            },
        )


def _digest(row: dict[str, object]) -> str:
    return content_hash(
        str(row.get("name") or ""),
        as_int(row.get("version")),
        str(row.get("sql") or ""),
        str(row.get("description") or ""),
    )


def subject_hash(store: Any, subject_id: uuid.UUID) -> str:
    """The digest of a stored version, worked out from its text. Reviews sign this."""
    row = store.saved_queries.get(subject_id)
    if not isinstance(row, dict):
        raise NotFoundError("subject not found")
    return _digest(row)
