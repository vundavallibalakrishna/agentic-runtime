"""A persisted identity, never a synthetic demo ID, owns a durable login."""

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from ar_api.auth.complete import LoginError, login_result
from ar_api.auth.dev_users import catalogue
from ar_api.auth.identity import resolve_login_identity
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import DevBinding


@pytest.mark.parametrize(
    "outcome",
    ["active", "unbound", "missing_tenant", "tenant_suspended", "missing_user", "user_suspended"],
)
async def test_login_resolves_persisted_identity_and_denies_inactive_accounts(
    outcome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChatService()
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    store.durable_engine = object()
    if outcome != "unbound":
        store.dev_binding = DevBinding(tenant_id, {"admin@dev.local": user_id})
    tenant = SimpleNamespace(id=tenant_id, status="active")
    user = SimpleNamespace(
        id=user_id, email="admin@dev.local", display_name="Persisted name", status="active"
    )
    if outcome == "tenant_suspended":
        tenant.status = "suspended"
    if outcome == "user_suspended":
        user.status = "deprovisioned"
    repo = SimpleNamespace(
        get_tenant=AsyncMock(return_value=None if outcome == "missing_tenant" else tenant),
        get_user_by_email=AsyncMock(return_value=None if outcome == "missing_user" else user),
    )
    effective = AsyncMock(return_value=(frozenset({"chat:use"}), frozenset({"member"})))
    audit = AsyncMock()
    contexts = []

    @asynccontextmanager
    async def transaction(ctx, *, engine):
        contexts.append(ctx)
        assert engine is store.durable_engine
        yield object()

    monkeypatch.setattr("ar_api.auth.identity.tenant_session", transaction)
    monkeypatch.setattr("ar_api.auth.identity.IdentityRepository", lambda session, ctx: repo)
    monkeypatch.setattr(
        "ar_api.auth.identity.IdentityService",
        lambda repo: SimpleNamespace(effective_for=effective),
    )
    monkeypatch.setattr("ar_api.auth.identity.record", audit)
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(state=SimpleNamespace(chat=store)),
            "state": {"request_id": "login-test"},
        }
    )
    result = login_result(catalogue()["admin@dev.local"], access_token="at", refresh_token="rt")  # noqa: S106
    if outcome == "active":
        resolved = await resolve_login_identity(request, result)
        assert resolved["user_id"] == str(user_id)
        assert resolved["tenant_id"] == str(tenant_id)
        assert resolved["display_name"] == "Persisted name"
        assert resolved["permissions"] == ["chat:use"]
        assert resolved["roles"] == ["member"]
        assert resolved["access_token"] == "at"  # noqa: S105
        assert resolved["refresh_token"] == "rt"  # noqa: S105
        assert contexts[0].tenant_id == tenant_id
        audit.assert_awaited_once()
        assert audit.call_args.kwargs["actor_id"] == str(user_id)
        assert audit.call_args.kwargs["tenant_id"] == tenant_id
        effective.assert_awaited_once_with(user_id)
    else:
        expected = outcome if outcome.endswith("suspended") else "tenant_not_found"
        with pytest.raises(LoginError, match=expected):
            await resolve_login_identity(request, result)
        audit.assert_not_awaited()
        effective.assert_not_awaited()
