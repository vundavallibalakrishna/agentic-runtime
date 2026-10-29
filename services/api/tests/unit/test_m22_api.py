"""HTTP surface for service connections and imports."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Notes", "version": "1"},
    "servers": [{"url": "https://example.com"}],
    "paths": {"/notes": {"get": {"operationId": "listNotes", "summary": "List notes"}}},
}


def _client(tenant: uuid.UUID | None = None, user: str | None = None) -> TestClient:
    app = create_application()
    principal = Principal(
        kind="user",
        id=user or str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def test_service_connection_is_hidden_from_another_tenant() -> None:
    client = _client()
    created = client.post(
        "/api/v1/service-connections",
        json={"name": "github", "kind": "bearer", "secret": "super-secret-token"},
    )
    assert created.status_code == 200, created.text
    body = created.text
    assert "super-secret-token" not in body
    connection_id = created.json()["id"]
    hidden = _client(tenant=uuid.uuid4()).get(f"/api/v1/service-connections/{connection_id}")
    assert hidden.status_code == 404
    other_user = _client(user=str(uuid.uuid4())).get(f"/api/v1/service-connections/{connection_id}")
    assert other_user.status_code == 404


def test_connection_lifecycle_and_openapi_import() -> None:
    client = _client()
    created = client.post(
        "/api/v1/service-connections",
        json={"name": "notes", "kind": "bearer", "secret": "super-secret-token"},
    )
    assert created.status_code == 200, created.text
    connection_id = created.json()["id"]
    listed = client.get("/api/v1/service-connections")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["name"] == "notes"
    assert "super-secret-token" not in listed.text
    patched = client.patch(
        f"/api/v1/service-connections/{connection_id}",
        json={"headerName": "X-Token"},
    )
    assert patched.status_code == 200, patched.text
    rotated = client.post(
        f"/api/v1/service-connections/{connection_id}:rotate",
        json={"secret": "rotated-secret-token"},
    )
    assert rotated.status_code == 200, rotated.text
    assert "rotated-secret-token" not in rotated.text
    tested = client.post(
        f"/api/v1/service-connections/{connection_id}:test",
        json={"url": "ftp://example.com/health"},
    )
    assert tested.status_code == 200
    assert tested.json()["ok"] is False
    blocked = client.post(f"/api/v1/service-connections/{connection_id}:authorize")
    assert blocked.status_code == 422
    oauth = client.post(
        "/api/v1/service-connections",
        json={
            "name": "userlogin",
            "kind": "oauth_authorization_code",
            "tokenUrl": "memory://tokens",
            "authorizeUrl": "https://example.com/authorize",
            "clientId": "ar",
        },
    )
    assert oauth.status_code == 200, oauth.text
    started = client.post(f"/api/v1/service-connections/{oauth.json()['id']}:authorize")
    assert started.status_code == 200, started.text
    granted = client.get(
        "/api/v1/service-connections/oauth/callback",
        params={"code": "good-code", "state": started.json()["state"]},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["status"] == "active"
    deleted = client.delete(f"/api/v1/service-connections/{connection_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    imported = client.post(
        "/api/v1/openapi-imports",
        json={"slug": "notesapi", "name": "Notes", "document": SPEC},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["status"] == "approved"


def test_openapi_preview_and_describe() -> None:
    client = _client()
    preview = client.post("/api/v1/openapi-imports:preview", json={"document": SPEC})
    assert preview.status_code == 200, preview.text
    assert preview.json()["total"] == 1
    described = client.post(
        "/api/v1/described-tools:preview",
        json={"description": "GET https://example.com/zen"},
    )
    assert described.status_code == 200, described.text
    assert described.json()["method"] == "GET"
    saved = client.post(
        "/api/v1/described-tools",
        json={"description": "GET https://example.com/zen", "slug": "zen", "name": "zen"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "approved"
