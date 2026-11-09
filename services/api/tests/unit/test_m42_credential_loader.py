"""The credential loader resolves API keys and SCIM tokens into principals. Stage B of M42."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from ar_api.auth import credentials
from ar_domain.identity.tokens import new_scim_token, new_split_api_key, sha256_hex


@asynccontextmanager
async def _fake_session(_reason: str):
    yield object()


def _patch_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(credentials, "platform_session", _fake_session)


async def _session_load(kind: str, value: str):
    return SimpleNamespace(kind=kind, value=value)  # sentinel for delegated kinds


def _grant(perms: tuple[str, ...]) -> tuple[object, object]:
    assignment = SimpleNamespace(
        principal_type="service_account",
        principal_id=None,  # filled per test
        scope_type="tenant",
        scope_id=None,
    )
    role = SimpleNamespace(key="custom", permissions=list(perms))
    return assignment, role


@pytest.mark.asyncio
async def test_service_account_key_builds_scoped_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    key_id, secret, prefix, digest = new_split_api_key()
    tenant_id, sa_id, key_row_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    row = SimpleNamespace(
        prefix=prefix, secret_hash=digest, key_format="split", revoked_at=None, expires_at=None,
        service_account_id=sa_id, user_id=None, scopes=["agents:read"], tenant_id=tenant_id,
        id=key_row_id,
    )
    assignment, role = _grant(("agents:read", "chat:use"))
    assignment.principal_id = sa_id
    monkeypatch.setattr(credentials, "resolve_api_key_by_prefix", _const(row))
    active = SimpleNamespace(status="active")
    monkeypatch.setattr(credentials, "resolve_tenant_by_id", _const(active))
    monkeypatch.setattr(
        credentials, "resolve_service_account_by_id",
        _const(SimpleNamespace(id=sa_id, status="active", name="bot")),
    )
    monkeypatch.setattr(credentials, "fetch_service_account_grants", _const([(assignment, role)]))

    loader = credentials.credential_loader(_session_load)
    principal = await loader("api_key", f"{key_id}.{secret}")
    assert principal is not None
    assert principal.kind == "service_account" and principal.tenant_id == tenant_id
    assert principal.auth_method == "api_key" and principal.api_key_id == key_row_id
    # scope ∩ permissions: only agents:read is allowed even though the role grants chat:use too.
    assert principal.allows("agents:read") is True
    assert principal.allows("chat:use") is False


@pytest.mark.asyncio
async def test_revoked_expired_wrong_secret_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    key_id, secret, prefix, digest = new_split_api_key()
    base = {
        "prefix": prefix,
        "secret_hash": digest,
        "key_format": "split",
        "service_account_id": uuid.uuid4(),
        "user_id": None,
        "scopes": [],
        "tenant_id": uuid.uuid4(),
        "id": uuid.uuid4(),
    }
    import datetime as _dt
    past = _dt.datetime(2000, 1, 1, tzinfo=_dt.UTC)
    loader = credentials.credential_loader(_session_load)

    monkeypatch.setattr(credentials, "resolve_api_key_by_prefix",
                        _const(SimpleNamespace(**base, revoked_at=past, expires_at=None)))
    assert await loader("api_key", f"{key_id}.{secret}") is None  # revoked

    monkeypatch.setattr(credentials, "resolve_api_key_by_prefix",
                        _const(SimpleNamespace(**base, revoked_at=None, expires_at=past)))
    assert await loader("api_key", f"{key_id}.{secret}") is None  # expired

    monkeypatch.setattr(credentials, "resolve_api_key_by_prefix",
                        _const(SimpleNamespace(**base, revoked_at=None, expires_at=None)))
    assert await loader("api_key", f"{key_id}.sk_wrongsecret") is None  # bad secret

    monkeypatch.setattr(credentials, "resolve_api_key_by_prefix", _const(None))
    assert await loader("api_key", f"{key_id}.{secret}") is None  # unknown prefix


@pytest.mark.asyncio
async def test_scim_token_builds_scim_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    full, prefix, digest = new_scim_token()
    row = SimpleNamespace(prefix=prefix, secret_hash=digest, revoked_at=None, expires_at=None,
                          tenant_id=uuid.uuid4(), id=uuid.uuid4())
    monkeypatch.setattr(credentials, "resolve_scim_token_by_prefix", _const(row))
    active = SimpleNamespace(status="active")
    monkeypatch.setattr(credentials, "resolve_tenant_by_id", _const(active))
    loader = credentials.credential_loader(_session_load)
    principal = await loader("scim", full)
    assert principal is not None and principal.auth_method == "scim"
    assert principal.allows("users:manage") is True
    assert sha256_hex(full) == digest


@pytest.mark.asyncio
async def test_session_kind_is_delegated(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = credentials.credential_loader(_session_load)
    result = await loader("session", "cookie-value")
    assert result.kind == "session" and result.value == "cookie-value"


def _const(value: object):
    async def _fn(*_args: object, **_kwargs: object) -> object:
        return value
    return _fn
