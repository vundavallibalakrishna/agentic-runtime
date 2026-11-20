"""The hidden collection a long on-the-fly file is indexed into.

One per tenant, slug ``uploads``. It is created the first time a strategy
must search a file the caller did not place in a collection. It is left out
of the collections grid.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ArError
from ar_domain.agents.access import Actor

if TYPE_CHECKING:
    from typing import Any

SLUG = "uploads"
_MARK = "uploads"


def is_system(row: dict[str, object]) -> bool:
    stats = row.get("stats")
    return isinstance(stats, dict) and stats.get("system") == _MARK


def find_uploads(store: Any, tenant_id: uuid.UUID) -> dict[str, object] | None:
    rows = getattr(store, "knowledge_collections", {})
    if not isinstance(rows, dict):
        return None
    for row in rows.values():
        if (
            isinstance(row, dict)
            and row.get("tenant_id") == tenant_id
            and str(row.get("slug") or "").lower() == SLUG
            and is_system(row)
        ):
            return row
    return None


def ensure_uploads(store: Any, actor: Actor) -> dict[str, object] | None:
    """The system collection, or None when this tenant cannot index yet."""
    found = find_uploads(store, actor.tenant_id)
    if found is not None:
        return found
    rows = getattr(store, "knowledge_collections", {})
    if isinstance(rows, dict) and any(
        isinstance(row, dict)
        and row.get("tenant_id") == actor.tenant_id
        and str(row.get("slug") or "").lower() == SLUG
        for row in rows.values()
    ):
        return None
    from ar_domain.knowledge.book import KnowledgeBook  # noqa: PLC0415

    powered = Actor(
        actor.tenant_id,
        actor.user_id,
        frozenset(actor.permissions) | frozenset({"knowledge:manage", "knowledge:read"}),
    )
    try:
        view = KnowledgeBook(store).create_collection(
            powered,
            {
                "slug": SLUG,
                "name": "Uploads",
                "visibility": "private",
                "description": "Files indexed because a task could not read them in one pass.",
            },
        )
    except ArError:
        return None
    collection_id = uuid.UUID(str(view.get("id")))
    row = store.knowledge_collections.get(collection_id)
    if not isinstance(row, dict):
        return None
    stats = dict(row.get("stats") or {})
    stats["system"] = _MARK
    row["stats"] = stats
    return row
