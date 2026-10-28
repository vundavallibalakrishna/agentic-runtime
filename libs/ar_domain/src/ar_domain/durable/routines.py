"""Persist routine definitions and accepted events alongside their runs."""

import hashlib
import uuid
from typing import TYPE_CHECKING

import orjson
from sqlalchemy.dialects.postgresql import insert

from ar_domain.routines.tables import Routine, RoutineEvent
from ar_domain.secrets.cached import save_cached_secret

if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession


async def save_routines(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        values = {key: value for key, value in row.items() if key in Routine.__table__.columns}
        secret = str(row.get("webhook_secret") or "")
        if secret:
            payload = orjson.dumps(
                {
                    "current": secret,
                    "previous": row.get("webhook_secret_previous") or "",
                    "previousUntil": row.get("webhook_secret_previous_until"),
                }
            )
            secret_id = uuid.uuid5(row["id"], hashlib.sha256(payload).hexdigest())
            await save_cached_secret(
                session,
                tenant_id=row["tenant_id"],
                secret_id=secret_id,
                value=payload,
                user_id=row["owner_user_id"],
            )
            values["webhook_secret_ref_id"] = secret_id
        stmt = insert(Routine).values(**values)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Routine.id],
                set_={
                    key: getattr(stmt.excluded, key)
                    for key in values
                    if key not in {"id", "tenant_id", "created_at"}
                },
                where=Routine.tenant_id == row["tenant_id"],
            )
        )


async def save_events(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        values = {key: value for key, value in row.items() if key in RoutineEvent.__table__.columns}
        stmt = insert(RoutineEvent).values(**values)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[RoutineEvent.id],
                set_={"status": stmt.excluded.status, "run_id": stmt.excluded.run_id},
                where=RoutineEvent.tenant_id == row["tenant_id"],
            )
        )
