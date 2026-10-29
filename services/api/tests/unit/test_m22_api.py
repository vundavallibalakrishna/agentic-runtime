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
