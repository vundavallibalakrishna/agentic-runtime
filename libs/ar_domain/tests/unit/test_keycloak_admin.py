"""The identity-provider admin client: lookups before creates, ids from ``Location``."""

import httpx
import orjson
import pytest

from ar_domain.identity.keycloak_admin import IdpError, KeycloakAdmin, admin_token, split_issuer

BASE = "http://idp.test"
REALM = f"{BASE}/admin/realms/main"


class _Provider:
    """Records each admin call and answers the way Keycloak does."""

    def __init__(self, *, organizations: list[dict[str, str]], users: list[dict[str, str]]) -> None:
        self.organizations = organizations
        self.users = users
        self.calls: list[tuple[str, str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = orjson.loads(request.content) if request.content else None
        self.calls.append((request.method, str(request.url).split("?")[0], body))
        assert request.headers["authorization"] == "Bearer token-1"
        path = str(request.url).split("?")[0].removeprefix(REALM)
        if request.method == "GET" and path == "/organizations":
            return httpx.Response(200, json=self.organizations)
        if request.method == "GET" and path == "/users":
            return httpx.Response(200, json=self.users)
        if request.method == "POST" and path == "/organizations":
            return httpx.Response(201, headers={"location": f"{REALM}/organizations/org-new"})
        if request.method == "POST" and path == "/users":
            return httpx.Response(201, headers={"location": f"{REALM}/users/user-new"})
        if request.method == "POST" and path.endswith("/members"):
            return httpx.Response(409, json={"errorMessage": "already a member"})
        if request.method == "PUT" and path.endswith("/reset-password"):
            return httpx.Response(204)
        return httpx.Response(500)


def _admin(provider: _Provider) -> KeycloakAdmin:
    client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
    return KeycloakAdmin(BASE, "main", "token-1", client)


async def test_a_new_tenant_gets_an_organization_an_account_and_a_password() -> None:
    provider = _Provider(organizations=[], users=[])
    admin = _admin(provider)
    organization = await admin.ensure_organization("Acme", "acme", "acme.example")
    user = await admin.ensure_user("ada@acme.example", "Ada", "Lovelace")
    await admin.add_member(organization, user)
    await admin.set_password(user, "a long password")
    assert (organization, user) == ("org-new", "user-new")
    created = [body for method, _, body in provider.calls if method == "POST"]
    assert created[0] == {
        "name": "Acme",
        "alias": "acme",
        "domains": [{"name": "acme.example", "verified": True}],
    }
    assert created[1]["emailVerified"] is True  # type: ignore[index]
    assert created[2] == "user-new"
    assert provider.calls[-1] == (
        "PUT",
        f"{REALM}/users/user-new/reset-password",
        {"type": "password", "value": "a long password", "temporary": False},
    )


async def test_an_existing_organization_and_account_are_reused() -> None:
    provider = _Provider(
        organizations=[{"id": "org-other", "alias": "acme-eu"}, {"id": "org-1", "alias": "acme"}],
        users=[{"id": "user-1", "email": "ada@acme.example"}],
    )
    admin = _admin(provider)
    assert await admin.ensure_organization("Acme", "acme", "acme.example") == "org-1"
    assert await admin.ensure_user("ada@acme.example", "Ada", "Lovelace") == "user-1"
    assert [method for method, _, _ in provider.calls] == ["GET", "GET"]


async def test_a_refused_call_names_the_step_and_not_the_request() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(403, json={"error": "forbidden"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    admin = KeycloakAdmin(BASE, "main", "token-1", client)
    with pytest.raises(IdpError) as raised:
        await admin.set_password("user-1", "a long password")
    assert raised.value.status == 403
    assert "a long password" not in str(raised.value)
    with pytest.raises(IdpError):
        await admin_token(BASE, "admin", "wrong", client=client)


@pytest.mark.asyncio
async def test_a_refusal_repeats_the_providers_own_reason() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            403, json={"error": "invalid_request", "error_description": "HTTPS required"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as client:
        with pytest.raises(IdpError) as raised:
            await admin_token("http://idp.example", "admin", "not-shown", client=client)
    assert raised.value.status == 403
    assert raised.value.reason == "HTTPS required"
    assert str(raised.value) == (
        'identity provider refused the admin sign-in with status 403 and said "HTTPS required"'
    )
    assert "not-shown" not in str(raised.value)


def test_the_issuer_gives_the_base_address_and_the_realm() -> None:
    assert split_issuer("http://localhost:8180/realms/agentic-runtime/") == (
        "http://localhost:8180",
        "agentic-runtime",
    )
    with pytest.raises(ValueError, match="realms"):
        split_issuer("http://localhost:8180/")
