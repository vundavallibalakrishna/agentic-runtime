"""A userid/password sign-in becomes a session only for an active person of the served tenant.

Task: M43. Sign-in is in-app: the password is checked against the user's stored hash and
roles/permissions come from the tenant's rows. These tests plug the demo tenant's identity
in, the way ``ar_testing.demo`` does for every API test.
"""

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from ar_api.auth.complete import LoginError
from ar_api.auth.identity import resolve_password_login
from ar_domain.db.context import Principal, TenantContext
from ar_domain.demo_ids import demo_id
from ar_domain.durable.bind import TenantBinding
from ar_domain.identity.seed import DEV_PASSWORD
from ar_testing.demo import demo_store
from ar_testing.demo_people import DEV_TENANT_ID, catalogue
from ar_testing.memory_identity import MemoryIdentityStore, memory_identity


def _served(slug: str = "dev") -> tuple[Request, object, MemoryIdentityStore]:
    """A request to an application that serves the demo tenant under this slug."""
    store = demo_store()
    store.tenant_binding = TenantBinding(
        DEV_TENANT_ID,
        slug,
        "Dev",
        "enterprise",
        {email: person.user_id for email, person in catalogue().items()},
    )
    ctx = TenantContext.from_principal(
        Principal(kind="system", id="test", tenant_id=DEV_TENANT_ID), "login-test"
    )
    identity = memory_identity(store, ctx).store
    state = SimpleNamespace(
        chat=store, identity_provider=lambda ctx: memory_identity(store, ctx).store
    )
    request = Request(
        {"type": "http", "app": SimpleNamespace(state=state), "state": {"request_id": "login-test"}}
    )
    return request, store, identity  # type: ignore[return-value]


async def test_a_person_signs_in_with_their_rows() -> None:
    request, store, _identity = _served()
    resolved = await resolve_password_login(request, "Approver@dev.local", DEV_PASSWORD)
    assert resolved["tenant_id"] == str(DEV_TENANT_ID)
    assert resolved["user_id"] == str(demo_id("approver"))
    assert resolved["email"] == "approver@dev.local"
    assert resolved["display_name"] == "Dev Approver"
    assert resolved["roles"] == ["approver"]
    assert "approvals:decide" in resolved["permissions"]
    assert "tenant:manage" not in resolved["permissions"]
    # Policy and approvals read the person's roles and name from the store.
    assert store.user_roles[demo_id("approver")] == {"approver"}  # type: ignore[attr-defined]
    assert store.display_names[demo_id("approver")] == "Dev Approver"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("approver@dev.local", "wrong-password"),
        ("stranger@dev.local", DEV_PASSWORD),
        ("ada@acme.example", DEV_PASSWORD),
        ("approver@dev.local", ""),
    ],
)
async def test_a_wrong_password_or_unknown_person_is_refused(email: str, password: str) -> None:
    request, _store, _identity = _served()
    with pytest.raises(LoginError, match="invalid_credentials"):
        await resolve_password_login(request, email, password)


async def test_a_person_with_no_password_cannot_sign_in() -> None:
    """An invited user who has not set a password has no hash, so no password works."""
    request, _store, identity = _served()
    identity.users[demo_id("member")].password_hash = None
    with pytest.raises(LoginError, match="invalid_credentials"):
        await resolve_password_login(request, "member@dev.local", DEV_PASSWORD)


async def test_a_suspended_tenant_or_person_cannot_sign_in() -> None:
    request, _store, identity = _served()
    identity.users[demo_id("member")].status = "suspended"
    with pytest.raises(LoginError, match="user_suspended"):
        await resolve_password_login(request, "member@dev.local", DEV_PASSWORD)
    request, _store, identity = _served()
    identity.tenant.status = "suspended"
    with pytest.raises(LoginError, match="tenant_suspended"):
        await resolve_password_login(request, "member@dev.local", DEV_PASSWORD)


async def test_an_application_that_serves_no_tenant_signs_nobody_in() -> None:
    """A process that has not attached to a tenant has no door at all."""
    request, store, _identity = _served()
    store.tenant_binding = None  # type: ignore[attr-defined]
    with pytest.raises(LoginError, match="invalid_credentials"):
        await resolve_password_login(request, "admin@dev.local", DEV_PASSWORD)
