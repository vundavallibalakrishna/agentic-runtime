"""Connector catalogue HTTP, including a cross-tenant 404."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client() -> tuple[TestClient, dict[str, uuid.UUID]]:
    app = create_application()
    holder = {"tenant": demo_id("tenant"), "user": demo_id("admin")}

    async def resolve(_scope: object) -> Principal:
        return Principal(
            kind="user",
            id=str(holder["user"]),
            tenant_id=holder["tenant"],
            permissions=PERMISSION_KEYS,
            team_permissions=frozenset(),
            auth_method="bearer",
            email="admin@dev.local",
            display_name="Dev Admin",
        )

    app.state.resolve_principal = resolve
    return TestClient(app), holder


def test_catalog_install_and_cross_tenant_404() -> None:
    client, holder = _client()
    listed = client.get("/api/v1/connectors")
    assert listed.status_code == 200
    slugs = {item["slug"] for item in listed.json()["items"]}
    assert "github" in slugs
    assert "notion" in slugs
    assert "servicenow" in slugs
    assert "aws" in slugs
    aws = next(item for item in listed.json()["items"] if item["slug"] == "aws")
    assert aws["verification"] == "not_live"
    assert aws["implementation"] == "built"
    notion = next(item for item in listed.json()["items"] if item["slug"] == "notion")
    assert notion["verification"] == "not_live"
    detail = client.get("/api/v1/connectors/github")
    assert detail.status_code == 200
    body = detail.json()
    assert body["registrationUrl"].startswith("https://github.com/")
    assert any(tool["risk"] == "W2" for tool in body["tools"])
    installed = client.post(
        "/api/v1/connectors/github:install",
        json={"connectionName": "public-read"},
    )
    assert installed.status_code == 200
    assert "secret" not in installed.text.lower() or "hasSecret" in installed.text
    install_id = installed.json()["install"]["id"]
    holder["tenant"] = uuid.uuid4()
    hidden = client.get(f"/api/v1/connector-installs/{install_id}")
    assert hidden.status_code == 404
    holder["tenant"] = demo_id("tenant")
    visible = client.get(f"/api/v1/connector-installs/{install_id}")
    assert visible.status_code == 200
