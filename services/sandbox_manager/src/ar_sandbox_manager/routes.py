"""Internal sandbox-manager routes. Spec: docs/05-contracts/internal-apis.md §4."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ar_common.errors import QuotaExceededError
from ar_common.time import utcnow
from ar_contracts.api_model import ApiModel
from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.readmodel.model import RepositoryReadModel
from ar_domain.sandboxes.runtime import reap, release_container
from ar_domain.sandboxes.service import SandboxBook
from ar_sandbox_manager.egress import check
from ar_sandbox_manager.service import assert_sandbox_start

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

router = APIRouter()


class EnsureBody(ApiModel):
    tenant_id: uuid.UUID
    scope: str = "conversation"
    scope_key: str = ""
    template_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


@asynccontextmanager
async def _tenant_store(request: Request, tenant_id: uuid.UUID) -> AsyncIterator[Any]:
    """The store for one tenant's request.

    The repository read model loads that tenant, and saves what the request changed when
    the block ends. The in-memory store of dev and tests is used as it is.
    """
    service = request.app.state.chat
    if isinstance(service, RepositoryReadModel):
        async with service.open(tenant_id) as unit:
            yield unit
        return
    yield service


async def _tenant_of(request: Request, sandbox_id: uuid.UUID) -> uuid.UUID | None:
    """The tenant that owns a computer, or ``None`` when there is no such computer."""
    service = request.app.state.chat
    if isinstance(service, RepositoryReadModel):
        return await service.resolve_tenant({"sandbox_id": sandbox_id})
    row = service.sandboxes.get(sandbox_id)
    tenant = row.get("tenant_id") if isinstance(row, dict) else None
    return tenant if isinstance(tenant, uuid.UUID) else None


async def _tenants(request: Request) -> list[uuid.UUID]:
    service = request.app.state.chat
    if isinstance(service, RepositoryReadModel):
        return await service.tenant_ids()
    found = {row.get("tenant_id") for row in service.sandboxes.values() if isinstance(row, dict)}
    return [tenant for tenant in found if isinstance(tenant, uuid.UUID)]


def _owner(row: dict[str, object]) -> Actor:
    tenant = row["tenant_id"]
    user = row.get("user_id")
    if not isinstance(tenant, uuid.UUID):
        raise TypeError("a computer has no tenant")
    return Actor(tenant, user if isinstance(user, uuid.UUID) else tenant, PERMISSION_KEYS)


@router.post("/internal/v1/sandboxes:ensure")
async def ensure(body: EnsureBody, request: Request) -> dict[str, object]:
    async with _tenant_store(request, body.tenant_id) as store:
        try:
            assert_sandbox_start(store, body.tenant_id, body.user_id, body.agent_id)
        except QuotaExceededError as exc:
            return {"status": "quota_exceeded", "detail": str(exc)}
        return SandboxBook(store).ensure(
            Actor(body.tenant_id, body.user_id or body.tenant_id, PERMISSION_KEYS),
            {
                "template_id": body.template_id,
                "scope": body.scope,
                "scope_key": body.scope_key,
                "conversation_id": body.conversation_id,
                "agent_id": body.agent_id,
            },
        )


@router.get("/internal/v1/sandboxes/{sandbox_id}")
async def get_one(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    tenant = await _tenant_of(request, sandbox_id)
    if tenant is None:
        return {"status": "not_found"}
    async with _tenant_store(request, tenant) as store:
        row = store.sandboxes.get(sandbox_id)
        if not isinstance(row, dict):
            return {"status": "not_found"}
        return {"sandbox_id": str(sandbox_id), "status": row.get("status")}


@router.post("/internal/v1/sandboxes/{sandbox_id}:suspend")
async def suspend(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    tenant = await _tenant_of(request, sandbox_id)
    if tenant is None:
        return {"status": "not_found"}
    async with _tenant_store(request, tenant) as store:
        row = store.sandboxes.get(sandbox_id)
        if not isinstance(row, dict):
            return {"status": "not_found"}
        return SandboxBook(store).suspend(_owner(row), sandbox_id)


@router.post("/internal/v1/sandboxes/{sandbox_id}:terminate")
async def terminate(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    tenant = await _tenant_of(request, sandbox_id)
    if tenant is None:
        return {"status": "not_found"}
    async with _tenant_store(request, tenant) as store:
        row = store.sandboxes.get(sandbox_id)
        if not isinstance(row, dict):
            return {"status": "not_found"}
        return SandboxBook(store).terminate(_owner(row), sandbox_id)


@router.post("/internal/v1/sandboxes/{sandbox_id}:release")
async def release(sandbox_id: uuid.UUID, request: Request) -> dict[str, str]:
    """Stop the container or pod behind a computer. The caller records what happened."""
    tenant = await _tenant_of(request, sandbox_id)
    if tenant is None:
        return {"status": "not_found"}
    async with _tenant_store(request, tenant) as store:
        row = store.sandboxes.get(sandbox_id)
        if not isinstance(row, dict):
            return {"status": "not_found"}
        release_container(store, row)
        return {"status": "released"}


@router.post("/internal/v1/sandboxes:reap")
async def reap_now(request: Request) -> dict[str, int]:
    """Suspend idle computers and end those past their lifetime, tenant by tenant."""
    total = {"suspended": 0, "terminated": 0}
    for tenant in await _tenants(request):
        async with _tenant_store(request, tenant) as store:
            done = reap(store, tenant_id=tenant)
        for key in total:
            total[key] += int(done.get(key, 0))
    return total


@router.get("/internal/v1/egress/check")
async def egress(sandbox_id: str, host: str, token: str, request: Request) -> Response:
    """Answer the proxy: may this computer reach this host. Anything unknown is refused."""
    try:
        key = uuid.UUID(sandbox_id)
    except ValueError:
        return Response(status_code=403)
    tenant = await _tenant_of(request, key)
    if tenant is None:
        return Response(status_code=403)
    async with _tenant_store(request, tenant) as store:
        return Response(status_code=check(store, sandbox_id, host, token))


@router.post("/internal/v1/sandboxes/{sandbox_id}:touch")
async def touch(sandbox_id: uuid.UUID, request: Request) -> dict[str, str]:
    tenant = await _tenant_of(request, sandbox_id)
    if tenant is None:
        return {"status": "not_found"}
    async with _tenant_store(request, tenant) as store:
        row = store.sandboxes.get(sandbox_id)
        if not isinstance(row, dict):
            return {"status": "not_found"}
        row["last_active_at"] = utcnow()
        return {"status": "ready"}
