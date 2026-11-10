"""Audit read API. Spec: docs/03-specs/17-audit-usage-metering.md §1.3.

The response is the hash-chained Postgres log when this process has a database.
Without one, tests may place chained rows on ``audit_api``. The process-local
``audit_log`` is not merged in: those rows are not chained.
"""

from typing import TYPE_CHECKING

import orjson
from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_api.state import as_object
from ar_common.errors import NotFoundError, ValidationFailedError
from ar_domain.audit.read import as_engine
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


router = APIRouter()

_MAX_RANGE = 1_000_000


@router.get("/api/v1/audit-events", dependencies=[Depends(require_permission("audit:read"))])
@expose(public=False, permission="audit:read")
async def list_events(request: Request) -> dict[str, object]:
    data = await _read(request)
    return {"data": data, "next_cursor": None}


@router.get(
    "/api/v1/audit-events/{event_id}", dependencies=[Depends(require_permission("audit:read"))]
)
@expose(public=False, permission="audit:read")
async def get_event(event_id: int, request: Request) -> dict[str, object]:
    found = await _one(request, event_id)
    if found is None:
        raise NotFoundError("audit event not found")
    return as_object(found)


@router.post(
    "/api/v1/audit-events:verify", dependencies=[Depends(require_permission("audit:read"))]
)
@expose(public=False, permission="audit:read")
async def verify(request: Request) -> dict[str, object]:
    start, end = await _range(request)
    engine, principal = _binding(request)
    if engine is not None and principal is not None and principal.tenant_id is not None:
        from ar_domain.audit.read import list_chain, verify_public_chain  # noqa: PLC0415

        ctx = TenantContext.from_principal(principal, _request_id(request))
        async with tenant_session(ctx, engine=engine) as session:
            rows = await list_chain(session, principal.tenant_id)
        return verify_public_chain(rows, from_seq=start, to_seq=end)
    return as_object(
        await request.app.state.audit_api.verify(
            tenant_id=None if principal is None else principal.tenant_id,
            from_seq=start,
            to_seq=end,
        )
    )


async def _read(request: Request) -> list[dict[str, object]]:
    engine, principal = _binding(request)
    if engine is not None and principal is not None and principal.tenant_id is not None:
        from ar_domain.audit.read import list_chain  # noqa: PLC0415

        ctx = TenantContext.from_principal(principal, _request_id(request))
        async with tenant_session(ctx, engine=engine) as session:
            return await list_chain(session, principal.tenant_id)
    tenant_id = None if principal is None else principal.tenant_id
    return list(await request.app.state.audit_api.list_events(tenant_id=tenant_id))


async def _one(request: Request, event_id: int) -> dict[str, object] | None:
    engine, principal = _binding(request)
    if engine is not None and principal is not None and principal.tenant_id is not None:
        from ar_domain.audit.read import get_chain_event  # noqa: PLC0415

        ctx = TenantContext.from_principal(principal, _request_id(request))
        async with tenant_session(ctx, engine=engine) as session:
            return await get_chain_event(session, principal.tenant_id, event_id)
    tenant_id = None if principal is None else principal.tenant_id
    found = await request.app.state.audit_api.get(event_id, tenant_id=tenant_id)
    return found if isinstance(found, dict) else None


def _binding(request: Request) -> tuple[AsyncEngine | None, Principal | None]:
    chat = getattr(request.app.state, "chat", None)
    bound = as_engine(getattr(chat, "durable_engine", None))
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        return bound, None
    return bound, principal


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "audit"))


async def _range(request: Request) -> tuple[int | None, int | None]:
    raw = await request.body()
    if not raw:
        return None, None
    loaded = orjson.loads(raw)
    if not isinstance(loaded, dict):
        raise ValidationFailedError("verification body must be an object")
    start = _seq(loaded.get("fromSeq", loaded.get("from_seq")))
    end = _seq(loaded.get("toSeq", loaded.get("to_seq")))
    if start is not None and end is not None and end - start > _MAX_RANGE:
        raise ValidationFailedError("verification range is too long")
    return start, end


def _seq(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationFailedError("sequence bounds are integers")
    return value
