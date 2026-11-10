"""Research HTTP, including a cross-tenant 404. Proof: unit (in-process client)."""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


def _client() -> tuple[TestClient, dict[str, uuid.UUID]]:
    app = demo_application()
    app.state.await_runs = True
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


def test_research_round_trip_and_cross_tenant_404() -> None:
    client, holder = _client()
    created = client.post(
        "/api/v1/research/runs",
        json={"question": "What do the stored notes say about a kite?"},
    )
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["sources"]
    assert body["sources"][0]["sha256"]
    run_id = body["runId"]
    assert client.get(f"/api/v1/research/runs/{run_id}").status_code == 200
    saved = client.put(
        "/api/v1/model-routes",
        json={
            "routes": [
                {
                    "id": "primary",
                    "baseUrl": "https://example.com/v1",
                    "model": "stub-model",
                    "secretName": "llm",
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["routes"][0]["secretName"] == "llm"
    assert "value" not in saved.json()["routes"][0]
    holder["tenant"] = uuid.uuid4()
    hidden = client.get(f"/api/v1/research/runs/{run_id}")
    assert hidden.status_code == 404


def test_events_output_and_resume_of_a_cancelled_run() -> None:
    client, _holder = _client()
    app = client.app
    created = client.post("/api/v1/research/runs", json={"question": "Notes about paper kites."})
    run_id = created.json()["runId"]
    missing = client.get(f"/api/v1/runs/{run_id}/outputs/missing")
    assert missing.status_code == 404
    listed = client.get("/api/v1/model-routes")
    assert listed.status_code == 200
    events = client.get(f"/api/v1/research/runs/{run_id}/events")
    assert events.status_code == 200
    assert "research.progress" in events.text or "run.completed" in events.text
    store = app.state.chat
    store.runs[uuid.UUID(run_id)]["status"] = "cancelled"
    resumed = client.post(f"/api/v1/research/runs/{run_id}:resume")
    assert resumed.status_code == 200


def test_external_research_with_an_agent_key() -> None:
    client, _holder = _client()
    agents = client.get("/api/v1/agents").json()
    rows = agents.get("items") or agents.get("data") or []
    agent_id = next(row["id"] for row in rows if row.get("slug") == "assistant")
    created = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "research"},
    )
    assert created.status_code == 200, created.text
    headers = {"Authorization": f"Bearer {created.json()['key']}"}
    started = client.post(
        "/v1/research/runs",
        headers=headers,
        json={"question": "What do the stored notes say about a kite?"},
    )
    assert started.status_code == 202, started.text
    run_id = started.json()["runId"]
    assert client.get(f"/v1/research/runs/{run_id}", headers=headers).status_code == 200
    hidden = client.get(f"/v1/research/runs/{uuid.uuid4()}", headers=headers)
    assert hidden.status_code == 404


def test_cancel_and_resume() -> None:
    client, _holder = _client()
    created = client.post("/api/v1/research/runs", json={"question": "Notes about paper kites."})
    run_id = created.json()["runId"]
    cancelled = client.post(f"/api/v1/research/runs/{run_id}:cancel")
    assert cancelled.status_code == 409
    resumed = client.post(f"/api/v1/research/runs/{run_id}:resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"
