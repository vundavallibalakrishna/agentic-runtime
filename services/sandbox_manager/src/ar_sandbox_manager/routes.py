"""Internal sandbox-manager routes. Spec: docs/05-contracts/internal-apis.md §4."""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ar_common.errors import QuotaExceededError
from ar_contracts.api_model import ApiModel
from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.sandboxes.runtime import reap
from ar_domain.sandboxes.service import SandboxBook
from ar_sandbox_manager.egress import check
from ar_sandbox_manager.service import assert_sandbox_start

router = APIRouter()


class EnsureBody(ApiModel):
    tenant_id: uuid.UUID
    scope: str = "conversation"
    scope_key: str = ""
    template_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


def _book(request: Request) -> SandboxBook:
    return SandboxBook(request.app.state.chat)


def _actor(body: EnsureBody) -> Actor:
    return Actor(body.tenant_id, body.user_id or body.tenant_id, PERMISSION_KEYS)


@router.post("/internal/v1/sandboxes:ensure")
async def ensure(body: EnsureBody, request: Request) -> dict[str, object]:
    try:
        assert_sandbox_start(request.app.state.chat, body.tenant_id, body.user_id, body.agent_id)
    except QuotaExceededError as exc:
        return {"status": "quota_exceeded", "detail": str(exc)}
    return _book(request).ensure(
        _actor(body),
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
    store = request.app.state.chat
    row = store.sandboxes.get(sandbox_id)
    if not isinstance(row, dict):
        return {"status": "not_found"}
    return {"sandbox_id": str(sandbox_id), "status": row.get("status")}


@router.post("/internal/v1/sandboxes/{sandbox_id}:suspend")
async def suspend(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    store = request.app.state.chat
    row = store.sandboxes.get(sandbox_id)
    tenant = row.get("tenant_id") if isinstance(row, dict) else None
    user = row.get("user_id") if isinstance(row, dict) else None
    if not isinstance(tenant, uuid.UUID):
        return {"status": "not_found"}
    who = Actor(tenant, user if isinstance(user, uuid.UUID) else tenant, PERMISSION_KEYS)
    return _book(request).suspend(who, sandbox_id)


@router.post("/internal/v1/sandboxes/{sandbox_id}:terminate")
async def terminate(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    store = request.app.state.chat
    row = store.sandboxes.get(sandbox_id)
    tenant = row.get("tenant_id") if isinstance(row, dict) else None
    user = row.get("user_id") if isinstance(row, dict) else None
    if not isinstance(tenant, uuid.UUID):
        return {"status": "not_found"}
    who = Actor(tenant, user if isinstance(user, uuid.UUID) else tenant, PERMISSION_KEYS)
    return _book(request).terminate(who, sandbox_id)


@router.post("/internal/v1/sandboxes:reap")
async def reap_now(request: Request) -> dict[str, int]:
    return reap(request.app.state.chat)


@router.get("/internal/v1/egress/check")
async def egress(sandbox_id: str, host: str, token: str, request: Request) -> Response:
    status = check(request.app.state.chat, sandbox_id, host, token)
    return Response(status_code=status)


@router.post("/internal/v1/sandboxes/{sandbox_id}:touch")
async def touch(sandbox_id: uuid.UUID, request: Request) -> dict[str, str]:
    from ar_common.time import utcnow  # noqa: PLC0415

    row = request.app.state.chat.sandboxes.get(sandbox_id)
    if isinstance(row, dict):
        row["last_active_at"] = utcnow()
        return {"status": "ready"}
    return {"status": "not_found"}
