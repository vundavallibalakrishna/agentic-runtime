"""Assurance screens and routes exist only for tenants that turn the feature on. Task: M32-T09."""

import uuid

from fastapi.testclient import TestClient

from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import ASSURANCE_PERMISSIONS, PERMISSION_KEYS
from ar_domain.identity.tenant_settings import feature_enabled, permissions_for_features
from ar_testing.demo import demo_application


def _principal(tenant: uuid.UUID) -> Principal:
    return Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=tenant,
        permissions=PERMISSION_KEYS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
        step_up_at=utcnow(),
    )


def _client(principal: Principal) -> TestClient:
    app = demo_application()

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_assurance_permissions_follow_the_tenant_flag() -> None:
    client = _client(_principal(demo_id("tenant")))
    store = client.app.state.chat
    off_tenant = uuid.uuid4()
    assert feature_enabled(store, demo_id("tenant"), "assurance", default=False) is True
    assert feature_enabled(store, off_tenant, "assurance", default=False) is False
    kept = permissions_for_features(store, demo_id("tenant"), PERMISSION_KEYS)
    assert ASSURANCE_PERMISSIONS <= kept
    stripped = permissions_for_features(store, off_tenant, PERMISSION_KEYS)
    assert not (ASSURANCE_PERMISSIONS & stripped)
    assert "chat:use" in stripped
    assert "evidence:read" in ASSURANCE_PERMISSIONS
    assert "guests:manage" in ASSURANCE_PERMISSIONS


def test_assurance_routes_are_not_found_until_the_feature_is_on() -> None:
    off_tenant = uuid.uuid4()
    client = _client(_principal(off_tenant))
    assert client.get("/api/v1/evidence").status_code == 404
    assert client.get("/api/v1/binders").status_code == 404
    assert client.get("/api/v1/tenant/packs").status_code == 200, "packs stay reachable"
    client.app.state.chat.tenant_settings[off_tenant] = {"features": {"assurance": True}}
    assert client.get("/api/v1/evidence").status_code == 200
    dev = _client(_principal(demo_id("tenant")))
    assert dev.get("/api/v1/evidence").status_code == 200


def test_session_reports_tenant_features_and_locale() -> None:
    client = _client(_principal(demo_id("tenant")))
    body = client.get("/api/v1/auth/session").json()
    assert body["features"]["assurance"] is True
    assert body["features"]["piiRedaction"] is True or body["features"]["pii_redaction"] is True
    assert body["user"]["locale"]
    assert body["user"]["timezone"]


def test_a_settings_patch_keeps_the_dev_tenants_assurance_flag() -> None:
    """The in-memory identity store and the chat store seed the same dev settings, so a
    patch from the Tools screen does not switch the assurance desk off (the web-e2e
    failure on PR 49)."""
    app = demo_application()
    app.state.chat.seed_showcase()
    client = TestClient(app, base_url="http://localhost:3000")
    client.post("/api/v1/auth/dev-login", data={"email": "admin@dev.local"}, follow_redirects=False)
    before = client.get("/api/v1/auth/session").json()
    assert before["features"]["assurance"] is True
    headers = {"X-CSRF-Token": before["csrfToken"], "Origin": "http://localhost:3000"}
    patched = client.patch(
        "/api/v1/tenant", headers=headers, json={"settings": {"chat": {"allowSharing": False}}}
    )
    assert patched.status_code == 200, patched.text
    after = client.get("/api/v1/auth/session").json()
    assert after["features"]["assurance"] is True
    assert after["features"]["assurance"] is True
    assert client.get("/api/v1/evidence").status_code == 200
