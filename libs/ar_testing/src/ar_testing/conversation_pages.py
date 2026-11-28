"""List repository stand-in registered explicitly by unit/browser-test setup."""

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from fastapi import Request

from ar_common.errors import InvalidCursorError
from ar_common.pagination import decode_cursor, encode_cursor
from ar_contracts.json_api import Page
from ar_domain.db.context import TenantContext


class MemoryConversationPages:
    """The same page contract over a test's own in-memory rows."""

    def __init__(self, store: Any, ctx: TenantContext) -> None:
        self.store = store
        self.ctx = ctx

    async def page(
        self,
        collection: str,
        *,
        secret: str,
        limit: int = 50,
        cursor: str | None = None,
        q: str = "",
        status: str | None = None,
        include_previews: bool = False,
    ) -> Page:
        term = q.strip()
        scope = hashlib.sha256(
            repr(
                (
                    str(self.ctx.tenant_id),
                    self.ctx.principal.id,
                    collection,
                    term,
                    status,
                    include_previews,
                )
            ).encode()
        ).hexdigest()
        stamp = "updated_at" if collection == "conversations" else "created_at"
        rows = [
            self.store._public(row)
            for row in getattr(self.store, collection).values()
            if row.get("tenant_id") == self.ctx.tenant_id
            and str(row.get("user_id")) == self.ctx.principal.id
            and (
                collection != "conversations"
                or (not row.get("deleted_at") and (include_previews or not row.get("is_preview")))
            )
        ]
        rows = [
            row
            for row in rows
            if (not status or row.get("status") == status)
            and (
                not term
                or term.lower()
                in " ".join(
                    str(row.get(key) or "")
                    for key in (
                        ["title", "id"]
                        if collection == "conversations"
                        else ["id", "trigger", "status", "result_summary"]
                    )
                ).lower()
            )
        ]
        rows.sort(key=lambda row: (str(row.get(stamp)), str(row["id"])), reverse=True)
        if cursor:
            keys, direction = decode_cursor(cursor, secret=secret)
            if len(keys) != 3 or keys[0] != scope or direction != "desc":
                raise InvalidCursorError
            rows = [
                row
                for row in rows
                if (str(row.get(stamp)), str(row["id"])) < (str(keys[1]), str(keys[2]))
            ]
        selected = rows[:limit]
        next_cursor = (
            encode_cursor(
                [scope, str(selected[-1][stamp]), str(selected[-1]["id"])],
                direction="desc",
                secret=secret,
            )
            if len(rows) > limit
            else None
        )
        return Page(items=selected, next_cursor=next_cursor, has_more=next_cursor is not None)


def install(app: Any) -> None:
    """Only a test's setup substitutes this repository dependency."""
    from ar_api.deps import current_principal, get_conversation_pages  # noqa: PLC0415

    async def repository(request: Request) -> MemoryConversationPages:
        return MemoryConversationPages(
            app.state.chat,
            TenantContext.from_principal(current_principal(request), str(request.state.request_id)),
        )

    app.dependency_overrides[get_conversation_pages] = repository
