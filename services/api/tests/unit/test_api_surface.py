"""Exercise the product API with in-memory ports.

Public JSON keys are camelCase. Error codes stay snake_case.
"""

import importlib.util
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ar_api.auth.csrf import csrf_ok, origin_ok
from ar_api.auth.oidc import authorize_url, new_pkce, safe_return_to
from ar_api.auth.session import MemorySessionStore, new_session, session_key_bytes
from ar_api.auth.step_up import require_step_up, step_up_fresh
from ar_api.main import create_application
from ar_api.principal import api_key_matches, api_key_prefix, classify_authorization, hash_text
from ar_api.ratelimit import MemoryTokenBucket, ValkeyTokenBucket
from ar_common.errors import ForbiddenError
from ar_common.settings import DeploymentMode
from ar_common.time import utcnow
from ar_domain.db.context import Principal, TenantContext
from ar_domain.identity.models import User
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.service import IdentityService
from ar_domain.identity.tokens import sha256_hex


def _mem_store() -> type:
    path = (
        Path(__file__).resolve().parents[4]
        / "libs"
        / "ar_domain"
        / "tests"
        / "unit"
        / "test_m1_domain.py"
    )
    spec = importlib.util.spec_from_file_location("m1_domain_mem", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._MemStore


def _principal(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    method: str = "api_key",
    permissions: frozenset[str] | None = None,
    tenant_status: str = "active",
    user_status: str = "active",
    kind: str = "user",
) -> Principal:
    return Principal(
        kind=kind,  # type: ignore[arg-type]
        id=str(user_id),
        tenant_id=tenant_id,
        permissions=PERMISSION_KEYS if permissions is None else permissions,
        auth_method=method,  # type: ignore[arg-type]
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
        tenant_status=tenant_status,
        user_status=user_status,
        csrf_token="csrf-token",  # noqa: S106
        session_id="sess-1",
    )


def _app(principal: Principal) -> TestClient:
    app = create_application()
    ctx = TenantContext.from_principal(principal, "req-test")
    store = _mem_store()(ctx)
    store.tenant.created_at = utcnow()
    store.add(
        User(
            id=ctx.user_id,
            tenant_id=ctx.tenant_id,
            idp_subject=principal.email or "",
            email=principal.email or "",
            display_name="Admin",
            status="active",
        )
    )
    app.state.identity_override = IdentityService(store)
    app.state.store = store

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.settings.deployment_mode = DeploymentMode.SAAS
    app.state.settings.saas_self_signup = True
    app.state.settings.webhook_allow_private = True
    return TestClient(app)


def test_public_helpers_and_session_round_trip() -> None:
    verifier, challenge = new_pkce()
    assert verifier and challenge
    assert safe_return_to("https://evil.example") == "/"
    assert safe_return_to("/admin") == "/admin"
    url = authorize_url(
        issuer="http://localhost:8180/realms/agentic-runtime",
        client_id="ar-web",
        redirect_uri="http://localhost:3000/api/v1/auth/callback",
        state="s",
        nonce="n",
        challenge=challenge,
        tenant="dev",
        idp="google",
    )
    assert "organization=dev" in url and "kc_idp_hint=google" in url
    assert csrf_ok("a", "a")
    assert not csrf_ok(None, "a")
    assert origin_ok(None, "http://localhost:3000")
    assert not origin_ok("http://evil.example", "http://localhost:3000")
    now = utcnow()
    assert not step_up_fresh(None, now=now, ttl_s=60)
    assert step_up_fresh(now, now=now, ttl_s=60)
    require_step_up(now, now=now, ttl_s=60, needed=False)
    key = session_key_bytes("", "cursor", prod=False)
    assert len(key) == 32
    try:
        session_key_bytes("aaaa", "cursor", prod=True)
    except RuntimeError:
        pass
    else:
        raise AssertionError("prod requires a 32-byte key")
    session_id, data = new_session(uuid.uuid4(), uuid.uuid4())
    store = MemorySessionStore(key)
    import asyncio

    asyncio.run(store.put(session_id, data, 60))
    loaded = asyncio.run(store.get(session_id))
    assert loaded is not None and loaded.csrf_token == data.csrf_token
    asyncio.run(store.delete(session_id))
    assert asyncio.run(store.get(session_id)) is None
    presented = classify_authorization("Bearer ark_abc", None)
    assert presented is not None and presented.kind == "api_key"
    assert classify_authorization("Bearer scim_abc", None).kind == "scim"  # type: ignore[union-attr]
    assert classify_authorization("Bearer eyJabc", None).kind == "bearer"  # type: ignore[union-attr]
    assert classify_authorization(None, "cookie").kind == "session"  # type: ignore[union-attr]
    assert classify_authorization("Basic x", None) is None
    token = "ark_" + "ab" * 6 + "secret"
    assert api_key_prefix(token) == "ab" * 6
    assert api_key_matches(token, sha256_hex(token))
    assert hash_text("x")


def test_rate_limit_window_and_valkey_fail_open() -> None:
    import asyncio

    bucket = MemoryTokenBucket()
    first = asyncio.run(bucket.take("k", 1, now=10))
    second = asyncio.run(bucket.take("k", 1, now=10))
    reset = asyncio.run(bucket.take("k", 1, now=70))
    assert first.allowed and not second.allowed and reset.allowed
    valkey = ValkeyTokenBucket("redis://127.0.0.1:1")
    opened = asyncio.run(valkey.take("k", 5))
    again = asyncio.run(valkey.take("k", 5))
    assert opened.allowed and again.allowed and valkey._open


def test_anonymous_is_rejected_and_meta_is_public() -> None:
    app = create_application()
    client = TestClient(app)
    assert client.get("/api/v1/meta").status_code == 200
    denied = client.get("/api/v1/me")
    assert denied.status_code == 401
    body = denied.json()
    assert body["code"] == "unauthenticated"
    assert "requestId" in body
    assert "_" not in "".join(body)


def test_identity_and_admin_surface_is_camel_case() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    client = _app(_principal(user_id, tenant_id))
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert "displayName" in me.json()
    patched = client.patch("/api/v1/me", json={"displayName": "Ava"})
    assert patched.status_code == 200
    assert patched.json()["displayName"] == "Ava"
    assert client.get("/api/v1/tenant").status_code == 200
    assert client.patch("/api/v1/tenant", json={"name": "Dev"}).status_code == 200
    users = client.get("/api/v1/users")
    assert users.status_code == 200
    assert "items" in users.json()
    assert client.get(f"/api/v1/users/{user_id}").status_code == 200
    assert client.patch(f"/api/v1/users/{user_id}", json={"status": "active"}).status_code == 200
    invited = client.post(
        "/api/v1/invitations",
        json={"emails": ["new@dev.local"], "roleKeys": ["member"]},
        headers={"Idempotency-Key": "invite-1"},
    )
    assert invited.status_code == 200, invited.text
    replay = client.post(
        "/api/v1/invitations",
        json={"emails": ["new@dev.local"], "roleKeys": ["member"]},
        headers={"Idempotency-Key": "invite-1"},
    )
    assert replay.headers.get("idempotent-replayed") == "true"
    conflict = client.post(
        "/api/v1/invitations",
        json={"emails": ["other@dev.local"], "roleKeys": ["member"]},
        headers={"Idempotency-Key": "invite-1"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_key_reused"
    assert client.get("/api/v1/invitations").status_code == 200
    invitation_id = invited.json()[0]["id"]
    token = invited.json()[0].get("token")
    if token:
        client.post(f"/api/v1/invitations/{token}:accept")
    assert client.delete(f"/api/v1/invitations/{invitation_id}").status_code in {200, 204, 404}
    group = client.post("/api/v1/groups", json={"name": "Ops"})
    assert group.status_code == 200, group.text
    group_id = group.json()["id"]
    assert client.get("/api/v1/groups").status_code == 200
    assert client.get(f"/api/v1/groups/{group_id}/members").status_code == 200
    assert client.put(f"/api/v1/groups/{group_id}/members/{user_id}").status_code in {200, 204}
    assert client.delete(f"/api/v1/groups/{group_id}/members/{user_id}").status_code in {200, 204}
    team = client.post("/api/v1/teams", json={"slug": "ops", "name": "Ops"})
    assert team.status_code == 200, team.text
    team_id = team.json()["id"]
    assert client.get(f"/api/v1/teams/{team_id}").status_code == 200
    renamed_team = client.patch(f"/api/v1/teams/{team_id}", json={"slug": "ops", "name": "Ops 2"})
    assert renamed_team.status_code == 200
    assert client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"userId": str(user_id), "teamRole": "member"},
    ).status_code in {200, 204}
    assert client.get("/api/v1/permissions").status_code == 200
    role = client.post(
        "/api/v1/roles",
        json={"key": "custom", "name": "Custom", "permissions": ["chat:use"]},
    )
    assert role.status_code == 200, role.text
    role_id = role.json()["id"]
    assert client.patch(f"/api/v1/roles/{role_id}", json={"name": "Custom 2"}).status_code == 200
    assignment = client.post(
        "/api/v1/role-assignments",
        json={
            "roleId": role_id,
            "principalType": "user",
            "principalId": str(user_id),
        },
    )
    assert assignment.status_code == 200, assignment.text
    assert client.get("/api/v1/role-assignments").status_code == 200
    assert client.delete(f"/api/v1/role-assignments/{assignment.json()['id']}").status_code in {
        200,
        204,
    }
    assert client.delete(f"/api/v1/roles/{role_id}").status_code in {200, 204}
    account = client.post("/api/v1/service-accounts", json={"name": "bot"})
    assert account.status_code == 200, account.text
    account_id = account.json()["id"]
    assert client.get("/api/v1/service-accounts").status_code == 200
    assert (
        client.patch(
            f"/api/v1/service-accounts/{account_id}", json={"description": "bot"}
        ).status_code
        == 200
    )
    created_key = client.post("/api/v1/api-keys", json={"name": "cli", "expiresInDays": 30})
    assert created_key.status_code == 200, created_key.text
    assert "key" in created_key.json()
    assert client.get("/api/v1/api-keys").status_code == 200
    assert client.delete(f"/api/v1/api-keys/{created_key.json()['id']}").status_code in {200, 204}
    assert client.delete(f"/api/v1/service-accounts/{account_id}").status_code in {200, 204}
    secret = client.post(
        "/api/v1/secrets", json={"name": "smtp", "value": "super-secret", "kind": "generic"}
    )
    assert secret.status_code == 200, secret.text
    assert "value" not in secret.json()
    secret_id = secret.json()["id"]
    assert client.get("/api/v1/secrets").status_code == 200
    assert client.get(f"/api/v1/secrets/{secret_id}").status_code == 200
    assert (
        client.patch(
            f"/api/v1/secrets/{secret_id}",
            json={"name": "smtp", "value": "super-secret", "description": "mail"},
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/secrets/{secret_id}:rotate", json={"value": "next"}).status_code
        == 200
    )
    domain = client.post("/api/v1/tenant/domains", json={"domain": "example.com"})
    assert domain.status_code == 200, domain.text
    domain_id = domain.json()["id"]
    assert client.get("/api/v1/tenant/domains").status_code == 200
    client.post(f"/api/v1/tenant/domains/{domain_id}:verify")
    idp = client.post(
        "/api/v1/identity-providers",
        json={
            "kind": "oidc",
            "displayName": "Okta",
            "config": {"issuer": "https://example.com"},
        },
    )
    assert idp.status_code in {200, 201, 422}, idp.text
    if idp.status_code < 300:
        idp_id = idp.json()["id"]
        client.get("/api/v1/identity-providers")
        client.patch(
            f"/api/v1/identity-providers/{idp_id}",
            json={"kind": "oidc", "displayName": "Okta 2", "config": {}},
        )
        client.delete(f"/api/v1/identity-providers/{idp_id}")
    token = client.post("/api/v1/scim-tokens")
    assert token.status_code == 200, token.text
    assert client.get("/api/v1/scim-tokens").status_code == 200
    client.delete(f"/api/v1/scim-tokens/{token.json()['id']}")
    grant = client.post(
        "/api/v1/tenant/support-access",
        json={
            "operatorSubject": "op",
            "operatorEmail": "op@example.com",
            "level": "metadata",
            "reason": "customer requested help",
            "hours": 4,
        },
    )
    assert grant.status_code == 200, grant.text
    assert client.get("/api/v1/tenant/support-access").status_code == 200
    client.post(f"/api/v1/tenant/support-access/{grant.json()['id']}:revoke")
    audit = client.get("/api/v1/audit-events")
    assert audit.status_code == 200
    verify = client.post("/api/v1/audit-events:verify")
    assert verify.status_code == 200
    assert verify.json()["ok"] is True
    note = client.app.state.notifications.add("Hello", "World")  # type: ignore[attr-defined]
    assert client.get("/api/v1/notifications").status_code == 200
    assert client.post(f"/api/v1/notifications/{note['id']}:read").status_code == 200
    assert client.post("/api/v1/notifications:read-all").status_code == 200
    hook = client.post(
        "/api/v1/webhooks",
        json={"name": "sink", "url": "https://example.com/hook", "topics": ["invitation.created"]},
    )
    assert hook.status_code == 200, hook.text
    hook_id = hook.json()["id"]
    assert client.get(f"/api/v1/webhooks/{hook_id}").status_code == 200
    assert (
        client.patch(
            f"/api/v1/webhooks/{hook_id}",
            json={"name": "sink", "url": "https://example.com/hook", "topics": ["*"]},
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/webhooks/{hook_id}:test").status_code in {200, 202}
    assert client.post(f"/api/v1/webhooks/{hook_id}:rotate-secret").status_code == 200
    assert client.get(f"/api/v1/webhooks/{hook_id}/deliveries").status_code == 200
    delivery_id = uuid.uuid4()
    assert (
        client.post(f"/api/v1/webhooks/{hook_id}/deliveries/{delivery_id}:redeliver").status_code
        == 200
    )
    assert client.post("/api/v1/tenant/run-callback-secret:rotate").status_code == 200
    client.delete(f"/api/v1/webhooks/{hook_id}")
    client.delete(f"/api/v1/secrets/{secret_id}")
    client.delete(f"/api/v1/tenant/domains/{domain_id}")
    client.delete(f"/api/v1/teams/{team_id}")
    client.delete(f"/api/v1/groups/{group_id}")
    signup = client.post("/api/v1/signup", json={"slug": "acme", "name": "Acme", "email": "a@b.c"})
    assert signup.status_code == 200
    assert "tenantId" in signup.json()
    platform = _app(_principal(user_id, tenant_id, kind="platform_admin"))
    created = platform.post(
        "/api/v1/platform/tenants",
        json={"slug": "acme", "name": "Acme", "planKey": "enterprise", "ownerEmail": "a@b.c"},
    )
    assert created.status_code == 202, created.text
    tenant = created.json()["tenantId"]
    assert platform.get("/api/v1/platform/tenants").status_code == 200
    assert platform.get(f"/api/v1/platform/tenants/{tenant}").status_code == 200
    assert platform.post(f"/api/v1/platform/tenants/{tenant}:suspend").status_code == 200
    assert platform.post(f"/api/v1/platform/tenants/{tenant}:resume").status_code == 200
    plan = platform.post(
        "/api/v1/platform/plans", json={"key": "plus", "name": "Plus", "limits": {}}
    )
    assert plan.status_code == 200, plan.text
    assert platform.get("/api/v1/platform/plans").status_code == 200
    plan_id = plan.json()["id"]
    renamed = platform.patch(
        f"/api/v1/platform/plans/{plan_id}",
        json={"key": "plus", "name": "Plus+"},
    )
    assert renamed.status_code == 200
    denied_platform = client.get("/api/v1/platform/tenants")
    assert denied_platform.status_code == 403
    login = client.get("/api/v1/auth/login", follow_redirects=False)
    assert login.status_code == 302
    state = login.headers["location"].split("state=")[1].split("&")[0]
    client.app.state.complete_login = _complete  # type: ignore[attr-defined]
    callback = client.get(f"/api/v1/auth/callback?code=abc&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert client.get("/api/v1/auth/session").status_code == 200
    switched = client.post("/api/v1/auth/switch-tenant", json={"tenant_id": str(tenant_id)})
    assert switched.status_code == 200
    assert client.post("/api/v1/auth/step-up", json={"return_to": "/admin"}).status_code == 200
    assert client.get("/api/v1/.well-known/jwks.json").status_code == 200
    assert client.get("/api/v1/schemas/agent").status_code in {200, 404}
    assert client.get("/api/v1/openapi.json").status_code == 200
    session_client = _app(_principal(user_id, tenant_id, method="session"))
    logged_out = session_client.post(
        "/api/v1/auth/logout",
        headers={"x-csrf-token": "csrf-token", "origin": "http://localhost:3000"},
    )
    assert logged_out.status_code == 200
    blocked = session_client.post("/api/v1/groups", json={"name": "nope"})
    assert blocked.status_code == 403
    limited = _app(_principal(user_id, tenant_id))
    limited.app.state.rate_limit = 1  # type: ignore[attr-defined]
    assert limited.get("/api/v1/me").status_code == 200
    assert limited.get("/api/v1/me").status_code == 429
    member = _app(_principal(user_id, tenant_id, permissions=frozenset()))
    assert member.get("/api/v1/users").status_code == 403
    suspended = _app(_principal(user_id, tenant_id, tenant_status="suspended"))
    assert suspended.get("/api/v1/me").status_code == 403
    inactive = _app(_principal(user_id, tenant_id, user_status="suspended"))
    assert inactive.get("/api/v1/me").status_code == 403
    long_key = client.post(
        "/api/v1/groups",
        json={"name": "x"},
        headers={"Idempotency-Key": "k" * 300},
    )
    assert long_key.status_code == 400
    stale = client.get("/api/v1/auth/callback?code=&state=missing", follow_redirects=False)
    assert stale.status_code == 302


async def _complete(code: str, saved: dict[str, object]) -> dict[str, str]:
    del code, saved
    return {
        "tenant_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "access_token": "a",
        "refresh_token": "r",
    }


def test_scim_and_platform_admin_and_single_tenant_hide() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    scim = _app(_principal(user_id, tenant_id, method="scim"))
    assert scim.get("/scim/v2/ServiceProviderConfig").status_code == 200
    assert scim.get("/scim/v2/Schemas").status_code == 200
    assert scim.get("/scim/v2/ResourceTypes").status_code == 200
    created = scim.post(
        "/scim/v2/Users",
        json={"userName": "scim@dev.local", "externalId": "ext-1"},
    )
    assert created.status_code == 200, created.text
    scim_user = created.json()["id"]
    listed = scim.get("/scim/v2/Users", params={"filter": 'userName eq "scim@dev.local"'})
    assert listed.status_code == 200
    assert listed.json()["totalResults"] >= 1
    assert scim.get(f"/scim/v2/Users/{scim_user}").status_code == 200
    assert (
        scim.patch(
            f"/scim/v2/Users/{scim_user}",
            json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
        ).status_code
        == 200
    )
    group = scim.post("/scim/v2/Groups", json={"displayName": "SCIM"})
    assert group.status_code == 200, group.text
    filtered = scim.get("/scim/v2/Groups", params={"filter": 'displayName eq "SCIM"'})
    assert filtered.status_code == 200
    scim.patch(
        f"/scim/v2/Groups/{group.json()['id']}",
        json={"Operations": [{"op": "add", "path": "members", "value": [{"value": str(user_id)}]}]},
    )
    denied = _app(_principal(user_id, tenant_id))
    assert denied.get("/scim/v2/Users").status_code == 401
    platform = _app(
        Principal(
            kind="platform_admin",
            id=str(user_id),
            tenant_id=tenant_id,
            permissions=PERMISSION_KEYS,
            auth_method="api_key",
            email="root@dev.local",
            tenant_status="suspended",
        )
    )
    assert platform.get("/api/v1/platform/tenants").status_code == 200
    assert platform.get("/api/v1/me").status_code == 403
    single = create_application()

    async def resolve(scope: object) -> Principal:
        del scope
        return _principal(user_id, tenant_id, kind="platform_admin")

    single.state.resolve_principal = resolve
    client = TestClient(single)
    assert client.get("/api/v1/platform/plans").status_code == 404
    hidden = client.post("/api/v1/signup", json={"slug": "a", "name": "A", "email": "a@b.c"})
    assert hidden.status_code == 404
    with pytest.raises(ForbiddenError):
        require_step_up(utcnow() - timedelta(hours=1), now=utcnow(), ttl_s=60, needed=True)
