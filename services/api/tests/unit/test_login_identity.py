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
from ar_domain.durable.bind import TenantBinding
from ar_testing.demo import demo_store


@pytest.mark.parametrize(
    "outcome",
    ["active", "unbound", "missing_tenant", "tenant_suspended", "missing_user", "user_suspended"],
)
async def test_login_resolves_persisted_identity_and_denies_inactive_accounts(
    outcome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = demo_store()
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    store.durable_engine = object()
    if outcome != "unbound":
        store.tenant_binding = TenantBinding(
            tenant_id, "acme", "Acme", "self_hosted", {"admin@dev.local": user_id}
        )
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


def _request(store: ChatService) -> Request:
    return Request(
        {
            "type": "http",
            "app": SimpleNamespace(state=SimpleNamespace(chat=store)),
            "state": {"request_id": "login-test"},
        }
    )


@pytest.mark.parametrize(
    ("organization", "admitted"),
    [("acme", True), ("ACME", True), ("", True), ("dev", False), ("other", False)],
)
async def test_the_token_organization_must_be_the_tenant_this_process_serves(
    organization: str, admitted: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task: M38b-T03. Nothing about the tenant or the person comes from code."""
    store = ChatService()
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    store.durable_engine = object()
    store.tenant_binding = TenantBinding(tenant_id, "acme", "Acme", "self_hosted", {})
    user = SimpleNamespace(
        id=user_id, email="Ada@Acme.Example", display_name="Ada Lovelace", status="active"
    )
    repo = SimpleNamespace(
        get_tenant=AsyncMock(return_value=SimpleNamespace(id=tenant_id, status="active")),
        get_user_by_email=AsyncMock(return_value=user),
    )
    effective = AsyncMock(return_value=(frozenset({"chat:use"}), frozenset({"tenant_admin"})))

    @asynccontextmanager
    async def transaction(ctx, *, engine):
        del ctx, engine
        yield object()

    monkeypatch.setattr("ar_api.auth.identity.tenant_session", transaction)
    monkeypatch.setattr("ar_api.auth.identity.IdentityRepository", lambda session, ctx: repo)
    monkeypatch.setattr(
        "ar_api.auth.identity.IdentityService",
        lambda repo: SimpleNamespace(effective_for=effective),
    )
    monkeypatch.setattr("ar_api.auth.identity.record", AsyncMock())
    claim = {"email": "ada@acme.example", "organization": organization, "access_token": "at"}
    if not admitted:
        with pytest.raises(LoginError, match="tenant_not_found"):
            await resolve_login_identity(_request(store), claim)
        repo.get_user_by_email.assert_not_awaited()
        assert store.user_roles == {}
        return
    resolved = await resolve_login_identity(_request(store), claim)
    assert resolved["tenant_id"] == str(tenant_id)
    assert resolved["user_id"] == str(user_id)
    assert resolved["roles"] == ["tenant_admin"]
    repo.get_user_by_email.assert_awaited_once_with("ada@acme.example")
    # Policy and approvals read the person's roles and name from the store.
    assert store.user_roles[user_id] == {"tenant_admin"}
    assert store.display_names[user_id] == "Ada Lovelace"
    assert store.user_emails[user_id] == "ada@acme.example"


async def test_a_store_without_a_database_admits_only_the_demo_tenant() -> None:
    store = demo_store()
    known = await resolve_login_identity(
        _request(store), {"email": "approver@dev.local", "organization": "dev"}
    )
    assert known["roles"] == ["approver"]
    with pytest.raises(LoginError, match="tenant_not_found"):
        await resolve_login_identity(
            _request(store), {"email": "ada@acme.example", "organization": "acme"}
        )
