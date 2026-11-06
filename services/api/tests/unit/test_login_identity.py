"""A sign-in becomes a session only for an active person of the tenant being served.

Tasks: M38b-T03, M38b-T05b. The application has one sign-in path. These tests plug the
demo tenant's identity into it, the way ``ar_testing.demo`` does for every API test.
"""

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from ar_api.auth.complete import LoginError
from ar_api.auth.identity import resolve_login_identity
from ar_domain.db.context import Principal, TenantContext
from ar_domain.demo_ids import demo_id
from ar_domain.durable.bind import TenantBinding
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


@pytest.mark.parametrize("organization", ["dev", "DEV", ""])
async def test_a_person_of_the_tenant_signs_in_with_their_rows(organization: str) -> None:
    request, store, _identity = _served()
    claim = {"email": "Approver@dev.local", "organization": organization, "access_token": "at"}
    resolved = await resolve_login_identity(request, claim)
    assert resolved["tenant_id"] == str(DEV_TENANT_ID)
    assert resolved["user_id"] == str(demo_id("approver"))
    assert resolved["email"] == "approver@dev.local"
    assert resolved["display_name"] == "Dev Approver"
    assert resolved["roles"] == ["approver"]
    assert "approvals:decide" in resolved["permissions"]
    assert "tenant:manage" not in resolved["permissions"]
    assert resolved["access_token"] == "at"  # noqa: S105
    # Policy and approvals read the person's roles and name from the store.
    assert store.user_roles[demo_id("approver")] == {"approver"}  # type: ignore[attr-defined]
    assert store.display_names[demo_id("approver")] == "Dev Approver"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("claim", "served"),
    [
        ({"email": "approver@dev.local", "organization": "acme"}, "dev"),
        ({"email": "approver@dev.local", "organization": "dev"}, "acme"),
        ({"email": "stranger@dev.local", "organization": "dev"}, "dev"),
        ({"email": "ada@acme.example", "organization": ""}, "dev"),
        ({"organization": "dev"}, "dev"),
    ],
)
async def test_anyone_else_is_refused(claim: dict[str, object], served: str) -> None:
    request, store, _identity = _served(served)
    with pytest.raises(LoginError, match="tenant_not_found"):
        await resolve_login_identity(request, claim)
    assert store.user_roles.keys() <= {person.user_id for person in catalogue().values()}  # type: ignore[attr-defined]


async def test_a_suspended_tenant_or_person_cannot_sign_in() -> None:
    claim = {"email": "member@dev.local", "organization": "dev"}
    request, _store, identity = _served()
    identity.users[demo_id("member")].status = "suspended"
    with pytest.raises(LoginError, match="user_suspended"):
        await resolve_login_identity(request, claim)
    request, _store, identity = _served()
    identity.tenant.status = "suspended"
    with pytest.raises(LoginError, match="tenant_suspended"):
        await resolve_login_identity(request, claim)


async def test_an_application_that_serves_no_tenant_signs_nobody_in() -> None:
    """A process that has not attached to a tenant has no door at all."""
    request, store, _identity = _served()
    store.tenant_binding = None  # type: ignore[attr-defined]
    with pytest.raises(LoginError, match="tenant_not_found"):
        await resolve_login_identity(request, {"email": "admin@dev.local", "organization": "dev"})
