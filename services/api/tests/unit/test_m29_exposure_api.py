"""HTTP surface for the external agent API."""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


def _principal(tenant: uuid.UUID | None = None) -> Principal:
    return Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
    )


def _client() -> tuple[TestClient, dict[str, Principal | None]]:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    app = demo_application()

    async def resolve(scope: object) -> Principal | None:
        del scope
        return holder["principal"]

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        run = app.state.chat.runs[run_id]
        run["status"] = "completed"
        assistant = app.state.chat.messages[run["assistant_message_id"]]
        assistant["text"] = "4"
        assistant["status"] = "completed"

    app.state.resolve_principal = resolve
    app.state.chat.generate = generate  # type: ignore[method-assign]
    agent = next(row for row in app.state.chat.agents.values() if row.get("slug") == "assistant")
    version = app.state.chat.versions[agent["published_version_id"]]
    definition = dict(version["definition"])
    definition["tools"] = [
        {"server": "session", "version": "*", "include": ["propose_change", "a2a_call"]}
    ]
    version["definition"] = definition
    return TestClient(app), holder


def _agent_id(client: TestClient) -> str:
    listed = client.get("/api/v1/agents")
    assert listed.status_code == 200
    rows = listed.json()["data"] if "data" in listed.json() else listed.json().get("items", [])
    assistant = next(row for row in rows if row["slug"] == "assistant")
    return str(assistant["id"])


def test_external_message_idempotency_revocation_and_isolation() -> None:
    client, holder = _client()
    agent_id = _agent_id(client)
    created = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "Proof", "rateLimitRpm": 10, "monthlyQuota": 20},
    )
    assert created.status_code == 200
    secret = created.json()["key"]
    assert secret.startswith("ara_")
    listed = client.get(f"/api/v1/agents/{agent_id}/exposure")
    assert listed.status_code == 200
    assert "key" not in listed.json()["keys"][0]
    assert listed.json()["endpoints"]["mcp"] == "/v1/mcp"
    missing = client.post("/v1/agents/assistant/conversations")
    assert missing.status_code == 401
    assert missing.json()["code"] == "unauthenticated"
    headers = {"Authorization": f"Bearer {secret}"}
    conversation = client.post("/v1/agents/assistant/conversations", headers=headers)
    assert conversation.status_code == 200
    conversation_id = conversation.json()["id"]
    body = {"text": "What is 2 + 2?"}
    idem = {"Idempotency-Key": "once"}
    first = client.post(
        f"/v1/agents/assistant/conversations/{conversation_id}/messages",
        headers={**headers, **idem},
        json=body,
    )
    assert first.status_code == 200
    assert first.json()["output"] == "4"
    second = client.post(
        f"/v1/agents/assistant/conversations/{conversation_id}/messages",
        headers={**headers, **idem},
        json=body,
    )
    assert second.status_code == 200
    assert second.headers.get("idempotent-replayed") == "true"
    assert second.json()["id"] == first.json()["id"]
    streamed = client.post(
        f"/v1/agents/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"text": "Again", "stream": True},
    )
    assert streamed.status_code == 200
    assert "text/event-stream" in streamed.headers["content-type"]
    assert "4" in streamed.text
    run_id = first.json()["id"]
    other = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "Other", "rateLimitRpm": 10},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['key']}"}
    hidden = client.get(f"/v1/agents/assistant/runs/{run_id}/events", headers=other_headers)
    assert hidden.status_code == 404
    holder["principal"] = _principal(tenant=uuid.uuid4())
    foreign = client.get(f"/api/v1/agents/{agent_id}/exposure")
    assert foreign.status_code == 404
    holder["principal"] = _principal()
    revoked = client.delete(f"/api/v1/agents/{agent_id}/api-keys/{created.json()['id']}")
    assert revoked.status_code == 200
    refused = client.post("/v1/agents/assistant/conversations", headers=headers)
    assert refused.status_code == 401
    assert "revoked" in refused.json()["detail"]


def test_rate_limit_mcp_and_a2a_card() -> None:
    client, _holder = _client()
    agent_id = _agent_id(client)
    created = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "Slow", "rateLimitRpm": 2},
    )
    headers = {"Authorization": f"Bearer {created.json()['key']}"}
    card = client.get("/v1/agents/assistant/.well-known/agent-card.json", headers=headers)
    assert card.status_code == 200
    assert client.get("/.well-known/agent-card.json", headers=headers).status_code == 200
    blocked = client.get("/v1/openapi.json")
    assert blocked.status_code == 200
    limited = client.get("/.well-known/agent-card.json", headers=headers)
    assert limited.status_code == 429
    assert limited.headers.get("retry-after")
    document = client.get("/v1/openapi.json").json()
    assert "/v1/agents/{slug}/conversations" in document["paths"]
    assert document["info"]["title"] == "Agentic Runtime Agent API"
    fresh = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "MCP", "rateLimitRpm": 20},
    )
    mcp_headers = {
        "Authorization": f"Bearer {fresh.json()['key']}",
        "Accept": "application/json",
    }
    listed = client.post(
        "/v1/mcp",
        headers=mcp_headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert listed.status_code == 200
    names = [item["name"] for item in listed.json()["result"]["tools"]]
    assert "agent_assistant" in names
    called = client.post(
        "/v1/mcp",
        headers=mcp_headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "agent_assistant",
                "arguments": {
                    "write": {
                        "tool": "session.propose_change",
                        "arguments": {"summary": "rename the record"},
                    }
                },
            },
        },
    )
    assert called.status_code == 200
    result = called.json()["result"]
    assert result["structuredContent"]["status"] == "approval_required"
    assert result["content"][0]["text"] == "Approval required"


def test_rotate_upload_events_and_unimplemented_a2a() -> None:
    client, _holder = _client()
    agent_id = _agent_id(client)
    created = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "Ops", "rateLimitRpm": 30},
    )
    secret = created.json()["key"]
    rotated = client.post(f"/api/v1/agents/{agent_id}/api-keys/{created.json()['id']}:rotate")
    assert rotated.status_code == 200
    assert rotated.json()["key"].startswith("ara_")
    headers = {"Authorization": f"Bearer {rotated.json()['key']}"}
    uploaded = client.post(
        "/v1/agents/assistant/files",
        headers=headers,
        files={"upload": ("note.txt", b"hello", "text/plain")},
        data={"mime_type": "text/plain"},
    )
    assert uploaded.status_code == 200
    conversation = client.post("/v1/agents/assistant/conversations", headers=headers)
    sent = client.post(
        f"/v1/agents/assistant/conversations/{conversation.json()['id']}/messages",
        headers=headers,
        json={"text": "hi", "attachmentIds": [uploaded.json()["id"]]},
    )
    assert sent.status_code == 200
    events = client.get(
        f"/v1/agents/assistant/runs/{sent.json()['id']}/events",
        headers=headers,
    )
    assert events.status_code == 200
    assert "text/event-stream" in events.headers["content-type"]
    sent = client.post(
        "/v1/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "hi"}]}},
        },
    )
    assert sent.status_code == 200
    task_id = sent.json()["result"]["id"]
    listed = client.post(
        "/v1/a2a",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tasks/list", "params": {"pageSize": 1}},
    )
    assert listed.status_code == 200
    assert listed.json()["result"]["tasks"]
    configured = client.post(
        "/v1/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tasks/pushNotificationConfig/set",
            "params": {
                "taskId": task_id,
                "pushNotificationConfig": {
                    "url": "http://127.0.0.1:9/push",
                    "token": "echo",
                },
            },
        },
    )
    assert configured.status_code == 200
    assert configured.json()["result"]["pushNotificationConfig"]["url"].endswith("/push")
    missing = client.post(
        "/v1/a2a",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 4, "method": "tasks/resubscribe"},
    )
    assert missing.status_code == 200
    assert missing.json()["error"]["code"] == -32000
    note = client.post(
        "/v1/mcp",
        headers={**headers, "Accept": "application/json"},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert note.status_code == 202
    streamed = client.post(
        "/v1/mcp",
        headers={**headers, "Accept": "text/event-stream"},
        json={"jsonrpc": "2.0", "id": 4, "method": "ping"},
    )
    assert streamed.status_code == 200
    assert "text/event-stream" in streamed.headers["content-type"]
    a2a_stream = client.post(
        "/v1/agents/assistant/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "message/stream",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "stream"}]}},
        },
    )
    assert a2a_stream.status_code == 200
    assert "event: task" in a2a_stream.text
    del secret
