"""Observability and evaluation HTTP surface."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _principal(
    *,
    tenant: uuid.UUID | None = None,
    permissions: frozenset[str] | None = None,
    roles: frozenset[str] = frozenset({"tenant_admin"}),
) -> Principal:
    return Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Admin",
        roles=roles,
    )


def _client(holder: dict[str, Principal]) -> TestClient:
    app = create_application()

    async def resolve(scope: object) -> Principal:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_overview_health_suites_and_isolation() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    overview = client.get("/api/v1/observability/overview")
    assert overview.status_code == 200
    assert "runs" in overview.json()
    health = client.get("/api/v1/platform/health")
    assert health.status_code == 200
    assert any(item["name"] == "postgres" for item in health.json()["components"])
    suites = client.get("/api/v1/eval-suites")
    assert suites.status_code == 200
    names = {item["name"] for item in suites.json()["items"]}
    assert "Prompt injection" in names
    created = client.post(
        "/api/v1/eval-suites",
        json={"name": "HTTP suite", "kind": "functional", "gate": {"required": False}},
    )
    assert created.status_code == 201
    suite_id = created.json()["id"]
    case = client.post(
        f"/api/v1/eval-suites/{suite_id}/cases",
        json={
            "name": "hello",
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "Say hello"}],
        },
    )
    assert case.status_code == 201
    run = client.post(f"/api/v1/eval-suites/{suite_id}:run", json={"agentVersionRef": "published"})
    assert run.status_code == 202
    assert run.json()["summary"]["passRate"] == 1
    holder["principal"] = _principal(tenant=uuid.uuid4())
    hidden = client.get(f"/api/v1/eval-suites/{suite_id}")
    assert hidden.status_code == 404
    holder["principal"] = _principal(permissions=frozenset({"chat:use"}))
    forbidden = client.get("/api/v1/eval-suites")
    assert forbidden.status_code == 403
    holder["principal"] = _principal(roles=frozenset({"member"}))
    denied = client.get("/api/v1/platform/health")
    assert denied.status_code == 403
