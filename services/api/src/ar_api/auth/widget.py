"""Restricted widget sessions; they never authenticate workspace endpoints."""

import uuid

from fastapi import Request

from ar_api.auth.session import SessionData
from ar_api.routers.tooling import chat
from ar_common.errors import NotFoundError, UnauthenticatedError
from ar_domain.audit.memory import remember
from ar_domain.audit.service import record
from ar_domain.channels.book import ChannelBook
from ar_domain.channels.widget_auth import widget_user
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.identity.repository import IdentityRepository


def integration(request: Request, integration_id: uuid.UUID | None) -> dict[str, object]:
    """Only active, enabled widget integrations can issue or use a session."""
    if integration_id is None:
        raise NotFoundError()
    book = ChannelBook(chat(request))
    row = book._integrations().get(integration_id)
    tenant_id = row.get("tenant_id") if isinstance(row, dict) else None
    if (
        not isinstance(row, dict)
        or row.get("kind") != "widget"
        or row.get("status") != "active"
        or not isinstance(tenant_id, uuid.UUID)
        or not book._enabled(tenant_id, "widget")
    ):
        raise NotFoundError()
    return row


async def active_user(request: Request, tenant_id: uuid.UUID, email: str) -> uuid.UUID | None:
    """Resolve an existing active user inside the integration's tenant."""
    store = chat(request)
    if store.durable_engine is None:
        return widget_user(store, tenant_id, email)
    principal = Principal(kind="system", id="widget", tenant_id=tenant_id)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with tenant_session(ctx, engine=store.durable_engine) as session:
        repo = IdentityRepository(session, ctx)
        tenant = await repo.get_tenant()
        user = await repo.get_user_by_email(email.lower())
        if tenant is None or tenant.status != "active" or user is None or user.status != "active":
            return None
        return user.id


async def widget_session_data(request: Request) -> SessionData:
    """Recheck expiry, integration revocation and user status on every request."""
    session_id = request.cookies.get("ar_widget_session", "")
    data = await request.app.state.widget_sessions.get(session_id)
    if not isinstance(data, SessionData) or data.widget_integration_id is None:
        raise UnauthenticatedError()
    row = integration(request, data.widget_integration_id)
    if row["tenant_id"] != data.tenant_id:
        raise NotFoundError()
    if await active_user(request, data.tenant_id, data.email) != data.user_id:
        raise UnauthenticatedError()
    return data


async def record_login(request: Request, data: SessionData) -> None:
    """Commit the authentication audit before releasing the session cookie."""
    store = chat(request)
    if store.durable_engine is None:
        remember(
            store,
            tenant_id=data.tenant_id,
            actor_id=data.user_id,
            action="auth.login",
            target_type="user",
            target_id=str(data.user_id),
            detail={"channel": "widget"},
        )
        return
    principal = Principal(kind="user", id=str(data.user_id), tenant_id=data.tenant_id)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with tenant_session(ctx, engine=store.durable_engine) as session:
        await record(
            session,
            tenant_id=data.tenant_id,
            actor_type="user",
            actor_id=str(data.user_id),
            action="auth.login",
            target_type="user",
            target_id=str(data.user_id),
            detail={"channel": "widget"},
        )


def agent_ids(row: dict[str, object]) -> set[uuid.UUID]:
    """The configured default and routing agents are the complete allowlist."""
    candidates = [row.get("default_agent_id")]
    routing = row.get("agent_routing")
    if isinstance(routing, list):
        candidates.extend(
            item.get("agent_id", item.get("agentId")) for item in routing if isinstance(item, dict)
        )
    found = set()
    for value in candidates:
        try:
            found.add(uuid.UUID(str(value)))
        except ValueError:
            continue
    return found


def check_conversation(request: Request, data: SessionData, conversation_id: uuid.UUID) -> None:
    """A widget can access only the conversation created for this session."""
    row = chat(request).conversations.get(conversation_id)
    if (
        conversation_id != data.widget_conversation_id
        or not isinstance(row, dict)
        or row.get("tenant_id") != data.tenant_id
        or row.get("user_id") != data.user_id
        or row.get("agent_id") not in agent_ids(integration(request, data.widget_integration_id))
    ):
        raise NotFoundError()
