"""Assurance screens and routes exist only for tenants that turn the feature on. Task: M32-T09."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import ASSURANCE_PERMISSIONS, PERMISSION_KEYS
from ar_domain.identity.tenant_settings import feature_enabled, permissions_for_features


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
    app = create_application()

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
