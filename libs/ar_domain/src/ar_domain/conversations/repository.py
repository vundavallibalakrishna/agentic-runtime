"""Bounded conversation/run reads under the caller's tenant transaction."""

import hashlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Text, cast, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import distinct_on

from ar_common.errors import InvalidCursorError
from ar_common.pagination import decode_cursor, encode_cursor
from ar_contracts.json_api import Page
from ar_domain.conversations.tables import Conversation, Message, Run
from ar_domain.db import BaseRepository

if TYPE_CHECKING:
    from typing import Literal


class ConversationRepository(BaseRepository):
    """List metadata without hydrating the tenant's conversations/messages/runs."""

    async def page(
        self,
        collection: Literal["conversations", "runs"],
        *,
        secret: str,
        limit: int = 50,
        cursor: str | None = None,
        q: str = "",
        status: str | None = None,
        include_previews: bool = False,
    ) -> Page:
        model = Conversation if collection == "conversations" else Run
        table = model.__table__
        stamp = model.updated_at if collection == "conversations" else model.created_at
        query = select(table).where(
            model.tenant_id == self.ctx.tenant_id,
            model.user_id == uuid.UUID(self.ctx.principal.id),
        )
        if collection == "conversations":
            query = query.where(Conversation.deleted_at.is_(None))
            if not include_previews:
                query = query.where(Conversation.is_preview.is_(False))
        if status:
            query = query.where(model.status == status)
        term = q.strip()
        if term:
            columns = (
                [Conversation.title, cast(Conversation.id, Text)]
                if collection == "conversations"
                else [cast(Run.id, Text), Run.trigger, Run.status, cast(Run.result_summary, Text)]
            )
            query = query.where(
                or_(*(column.icontains(term, autoescape=True) for column in columns))
            )
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
        if cursor:
            point, identity = _position(cursor, secret, scope)
            query = query.where(tuple_(stamp, model.id) < tuple_(point, identity))
        rows = list(
            (
                await self.session.execute(
                    query.order_by(stamp.desc(), model.id.desc()).limit(limit + 1)
                )
            ).mappings()
        )
        more = len(rows) > limit
        selected = rows[:limit]
        items = [dict(row) for row in selected]
        if collection == "runs" and items:
            await self._enrich_runs(items)
        next_cursor = None
        if more and selected:
            last = selected[-1]
            next_cursor = encode_cursor(
                [scope, last[stamp.key].isoformat(), str(last["id"])],
                direction="desc",
                secret=secret,
            )
        # JSON-mode serialization preserves the existing camelCase page contract at the edge.
        return Page(items=items, next_cursor=next_cursor, has_more=more)

    async def _enrich_runs(self, items: list[dict[str, object]]) -> None:
        # Fetch enrichment only for the selected page, never all messages in the tenant.
        ids = [row["id"] for row in items]
        labels = (
            await self.session.execute(
                select(Message.run_id, Message.answered_model)
                .where(
                    Message.tenant_id == self.ctx.tenant_id,
                    Message.run_id.in_(ids),
                    Message.role == "assistant",
                    Message.answered_model.is_not(None),
                    func.btrim(Message.answered_model) != "",
                )
                .ext(distinct_on(Message.run_id))
                .order_by(Message.run_id, Message.created_at.desc(), Message.id.desc())
            )
        ).all()
        named = {str(run_id): label.strip() for run_id, label in labels if label}
        previews = set(
            (
                await self.session.execute(
                    select(Conversation.id).where(
                        Conversation.tenant_id == self.ctx.tenant_id,
                        Conversation.id.in_([row["conversation_id"] for row in items]),
                        Conversation.is_preview.is_(True),
                    )
                )
            ).scalars()
        )
        for item in items:
            if named.get(str(item["id"])):
                item["answered_model"] = named[str(item["id"])]
            if item["conversation_id"] in previews:
                item["label"] = "preview"


def _position(cursor: str, secret: str, scope: str) -> tuple[datetime, uuid.UUID]:
    keys, direction = decode_cursor(cursor, secret=secret)
    if direction != "desc" or len(keys) != 3 or keys[0] != scope:
        raise InvalidCursorError
    try:
        point = datetime.fromisoformat(str(keys[1]))
        identity = uuid.UUID(str(keys[2]))
    except (ValueError, TypeError) as exc:
        raise InvalidCursorError from exc
    if point.tzinfo is None:
        raise InvalidCursorError
    return point, identity
