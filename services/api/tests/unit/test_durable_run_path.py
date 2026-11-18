"""Entry points start AgentRunWorkflow. Cancel and resume signal that workflow."""

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


class _Temporal:
    def __init__(self) -> None:
        self.started: list[dict[str, object]] = []
        self.signals: list[tuple[str, object]] = []

    async def start_workflow(self, workflow: object, payload: object, **kwargs: object) -> None:
        self.started.append(
            {
                "workflow": workflow,
                "payload": payload,
                "id": kwargs.get("id"),
                "task_queue": kwargs.get("task_queue"),
            }
        )

    def get_workflow_handle(self, workflow_id: str) -> _Temporal:
        self.handle_id = workflow_id
        return self

    async def signal(self, name: str, payload: object = None) -> None:
        self.signals.append((name, payload))

    async def describe(self) -> object:
        return SimpleNamespace(status=SimpleNamespace(name="RUNNING"))


def _app() -> tuple[TestClient, _Temporal]:
    app = demo_application()
    temporal = _Temporal()
    app.state.await_runs = True
    app.state.chat.temporal_client = temporal
    app.state.chat.watch_polls = 0
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(_scope: object) -> Principal:
        return principal

    app.state.resolve_principal = resolve
    return TestClient(app), temporal


def _agent_key(client: TestClient) -> dict[str, str]:
    agents = client.get("/api/v1/agents").json()
    rows = agents.get("items") or agents.get("data") or []
    agent_id = next(row["id"] for row in rows if row.get("slug") == "assistant")
    created = client.post(f"/api/v1/agents/{agent_id}/api-keys", json={"label": "durable"})
    assert created.status_code == 200, created.text
    return {"Authorization": f"Bearer {created.json()['key']}"}


def test_external_run_and_messages_start_agent_run_workflow() -> None:
    client, temporal = _app()
    headers = _agent_key(client)
    once = client.post(
        "/v1/agents/assistant:run",
        headers=headers,
        json={"text": "What is 2 + 2?"},
    )
    assert once.status_code == 200, once.text
    conversation = client.post("/v1/agents/assistant/conversations", headers=headers)
    sent = client.post(
        f"/v1/agents/assistant/conversations/{conversation.json()['id']}/messages",
        headers=headers,
        json={"text": "hello"},
    )
    assert sent.status_code == 200, sent.text
    assert len(temporal.started) == 2
    for started in temporal.started:
        assert started["workflow"] == "AgentRunWorkflow"
        assert started["task_queue"] == "ar-runtime"
        payload = started["payload"]
        assert isinstance(payload, dict)
        assert payload["steps"] is True
        assert str(started["id"]).startswith("run-")


def test_chat_and_research_start_the_same_workflow() -> None:
    client, temporal = _app()
    created = client.post("/api/v1/conversations", json={})
    assert created.status_code == 200, created.text
    posted = client.post(
        f"/api/v1/conversations/{created.json()['id']}/messages",
        json={"text": "Hello there"},
    )
    assert posted.status_code == 202, posted.text
    research = client.post("/api/v1/research/runs", json={"question": "Where do kites fly?"})
    assert research.status_code == 202, research.text
    assert [item["workflow"] for item in temporal.started] == [
        "AgentRunWorkflow",
        "AgentRunWorkflow",
    ]
    research_payload = temporal.started[1]["payload"]
    assert isinstance(research_payload, dict)
    assert research_payload["max_steps"] >= 1


def test_cancel_signals_the_workflow_and_resume_starts_it_again() -> None:
    client, temporal = _app()
    created = client.post("/api/v1/conversations", json={})
    posted = client.post(
        f"/api/v1/conversations/{created.json()['id']}/messages",
        json={"text": "keep going"},
    )
    run_id = posted.json()["run"]["id"]
    store = client.app.state.chat
    store.runs[uuid.UUID(run_id)]["status"] = "running"
    cancelled = client.post(f"/api/v1/runs/{run_id}:cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert store.runs[uuid.UUID(run_id)].get("cancel_requested") is True
    names = [name for name, _payload in temporal.signals]
    assert "cancel" in names
    store.runs[uuid.UUID(run_id)]["status"] = "failed"
    store.runs[uuid.UUID(run_id)]["checkpoint"] = {"worker_loop": {"opened": True, "steps": 1}}
    before = len(temporal.started)
    resumed = client.post(f"/api/v1/runs/{run_id}:resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "running"
    assert len(temporal.started) == before + 1
    assert temporal.started[-1]["workflow"] == "AgentRunWorkflow"
    assert temporal.started[-1]["id"] == f"run-{run_id}"
