"""M2 HTTP behaviour against the in-process chat store."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_common.settings import EnvName
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.files.logic import EICAR
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client(
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    kind: str = "user",
) -> TestClient:
    app = create_application()
    tenant = tenant_id or demo_id("tenant")
    user = user_id or demo_id("admin")
    principal = Principal(
        kind=kind,  # type: ignore[arg-type]
        id=str(user),
        tenant_id=tenant,
        permissions=PERMISSION_KEYS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    app.state.chat.scanner = "clamav"
    return TestClient(app)


def test_chat_round_trip_and_cross_tenant() -> None:
    client = _client()
    agents = client.get("/api/v1/agents")
    assert agents.status_code == 200
    assert agents.json()["items"][0]["slug"] == "assistant"
    created = client.post("/api/v1/conversations", json={})
    assert created.status_code == 200
    conversation_id = created.json()["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "Hello there"},
    )
    assert posted.status_code == 202
    run_id = posted.json()["run"]["id"]
    run = client.get(f"/api/v1/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert "fake:" in run.json()["resultSummary"]
    again = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "second"},
    )
    assert again.status_code == 202
    service = client.app.state.chat
    service.tasks.clear()
    conversation = uuid.UUID(conversation_id)
    service.runs[uuid.UUID(run_id)]["status"] = "running"
    service.conversations[conversation]["active_run_id"] = uuid.UUID(run_id)
    blocked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "nope"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "run_in_progress"
    service.runs[uuid.UUID(run_id)]["status"] = "completed"
    service.conversations[conversation]["active_run_id"] = None
    other = _client(uuid.uuid4(), uuid.uuid4())
    hidden = other.get(f"/api/v1/conversations/{conversation_id}")
    assert hidden.status_code == 404


def test_models_files_and_dev_login() -> None:
    client = _client()
    denied = client.post(
        "/api/v1/model-providers",
        json={"name": "private", "kind": "openai_compatible", "baseUrl": "http://10.1.1.1/v1"},
    )
    assert denied.status_code == 400
    created = client.post(
        "/api/v1/model-providers",
        json={"name": "local", "kind": "fake", "baseUrl": "http://127.0.0.1:8099/v1"},
    )
    assert created.status_code == 200
    tested = client.post(f"/api/v1/model-providers/{created.json()['id']}:test")
    assert tested.status_code == 200
    assert "output" in tested.json()
    upload = client.post(
        "/api/v1/files:upload",
        files={"upload": ("notes.pdf", b"%PDF-1.4 demo", "application/pdf")},
        data={"mime_type": "application/pdf"},
    )
    assert upload.status_code == 200
    assert upload.json()["status"] == "ready"
    infected = client.post(
        "/api/v1/files:upload",
        files={"upload": ("eicar.txt", EICAR, "text/plain")},
        data={"mime_type": "text/plain"},
    )
    assert infected.status_code == 200
    assert infected.json()["status"] == "quarantined"
    rejected = client.post(
        "/api/v1/files:upload",
        files={"upload": ("app.exe", b"MZ", "application/octet-stream")},
        data={"mime_type": "application/octet-stream"},
    )
    assert rejected.status_code == 415
    anonymous = TestClient(create_application())
    login = anonymous.post("/api/v1/auth/dev-login", follow_redirects=False)
    assert login.status_code == 303
    assert login.headers["location"] == "/chat"
    anonymous.app.state.settings.env = EnvName.PROD
    anonymous.cookies.clear()
    denied = anonymous.post("/api/v1/auth/dev-login", follow_redirects=False)
    assert denied.status_code == 404


def test_regenerate_share_and_callback_guard() -> None:
    client = _client()
    conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "branch me"},
    )
    message_id = posted.json()["message"]["id"]
    edited = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}:edit",
        json={"text": "edited"},
    )
    assert edited.status_code == 202
    detail = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    exported = client.get(f"/api/v1/conversations/{conversation_id}/export")
    assert exported.status_code == 200
    assert exported.json()["format"] == "markdown"
    viewer_id = uuid.uuid4()
    share = client.post(
        f"/api/v1/conversations/{conversation_id}/shares",
        json={"principalType": "user", "principalId": str(viewer_id)},
    )
    assert share.status_code == 200
    viewer = _client(demo_id("tenant"), viewer_id)
    viewer.app.state.chat = client.app.state.chat
    forbidden = viewer.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "no"},
    )
    assert forbidden.status_code == 403
    run = client.post(
        "/api/v1/runs",
        json={
            "agentId": client.get("/api/v1/agents").json()["items"][0]["id"],
            "text": "api",
            "onBehalfOfUserId": str(uuid.uuid4()),
            "allowOnBehalfOf": False,
        },
    )
    assert run.status_code == 403
    missing = client.post(f"/api/v1/runs/{uuid.uuid4()}:input")
    assert missing.status_code == 404


def test_catalogue_and_run_surface() -> None:
    client = _client()
    providers = client.get("/api/v1/model-providers")
    assert providers.status_code == 200
    created = client.post(
        "/api/v1/model-providers",
        json={"name": "desk", "kind": "fake", "baseUrl": "http://127.0.0.1:8099/v1"},
    )
    provider_id = created.json()["id"]
    renamed = client.patch(f"/api/v1/model-providers/{provider_id}", json={"name": "desk-2"})
    assert renamed.status_code == 200
    model = client.post(
        "/api/v1/models",
        json={
            "providerId": provider_id,
            "name": "desk-chat",
            "upstreamModel": "fake-chat",
            "kind": "chat",
        },
    )
    assert model.status_code == 200
    assert client.get("/api/v1/models").status_code == 200
    alias = client.post(
        "/api/v1/model-aliases",
        json={"alias": "desk", "kind": "chat", "primaryModelId": model.json()["id"]},
    )
    assert alias.status_code == 200
    assert client.get("/api/v1/model-aliases").status_code == 200
    tested = client.post(
        f"/api/v1/model-aliases/{alias.json()['id']}:test",
        json={"messages": [{"role": "user", "content": "ping"}]},
    )
    assert tested.status_code == 200
    agent = client.post("/api/v1/agents", json={"slug": "desk", "name": "Desk"})
    agent_id = agent.json()["id"]
    assert client.get(f"/api/v1/agents/{agent_id}").status_code == 200
    draft = client.put(
        f"/api/v1/agents/{agent_id}/versions/draft",
        json={
            "definition": {
                "persona": {"displayName": "Desk"},
                "instructions": "Be brief.",
                "model": {"alias": "reasoning"},
                "budget": {"maxSteps": 4, "maxTokens": 1000},
            }
        },
    )
    assert draft.status_code == 200
    assert client.get(f"/api/v1/agents/{agent_id}/versions").status_code == 200
    published = client.post(f"/api/v1/agents/{agent_id}:publish")
    assert published.status_code == 200
    conversation_id = client.post("/api/v1/conversations", json={"agentId": agent_id}).json()["id"]
    assert client.get("/api/v1/conversations").status_code == 200
    titled = client.patch(
        f"/api/v1/conversations/{conversation_id}", json={"title": "Desk", "pinned": True}
    )
    assert titled.status_code == 200
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"text": "status please"}
    )
    message_id = posted.json()["message"]["id"]
    run_id = posted.json()["run"]["id"]
    regenerated = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}:regenerate"
    )
    assert regenerated.status_code == 202
    activated = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}:activate"
    )
    assert activated.status_code == 200
    feedback = client.put(
        f"/api/v1/messages/{message_id}/feedback", json={"rating": "up", "comment": "ok"}
    )
    assert feedback.status_code == 200
    assert client.delete(f"/api/v1/messages/{message_id}/feedback").status_code == 200
    assert client.get(f"/api/v1/conversations/{conversation_id}/shares").status_code == 200
    viewer = str(uuid.uuid4())
    client.post(
        f"/api/v1/conversations/{conversation_id}/shares",
        json={"principalType": "user", "principalId": viewer},
    )
    removed = client.delete(f"/api/v1/conversations/{conversation_id}/shares/user/{viewer}")
    assert removed.status_code == 200
    exported = client.get(f"/api/v1/conversations/{conversation_id}/export?format=json")
    assert exported.json()["format"] == "json"
    upload = client.post(
        "/api/v1/files:upload",
        files={"upload": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
        data={"mime_type": "application/pdf"},
    )
    file_id = upload.json()["id"]
    assert client.get(f"/api/v1/files/{file_id}").status_code == 200
    content = client.get(f"/api/v1/files/{file_id}/content")
    assert content.status_code == 200
    assert client.delete(f"/api/v1/files/{file_id}").status_code == 200
    assert client.get("/api/v1/runs").status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}/steps").status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}/tool-calls").status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}/children").status_code == 200
    blocked = client.post(f"/api/v1/runs/{run_id}:input")
    assert blocked.status_code == 409
    finished = client.post(f"/api/v1/runs/{run_id}:cancel")
    assert finished.status_code == 409
    service = client.app.state.chat
    streaming = client.get(f"/api/v1/runs/{run_id}/events", headers={"last-event-id": "999"})
    assert streaming.status_code == 200
    service.sse_counts[str(demo_id("admin"))] = 20
    limited = client.get(f"/api/v1/runs/{run_id}/events")
    assert limited.status_code == 429
    assert client.delete(f"/api/v1/models/{model.json()['id']}").status_code == 200
    assert client.delete(f"/api/v1/model-providers/{provider_id}").status_code == 200
    assert client.delete(f"/api/v1/conversations/{conversation_id}").status_code == 200
    admin = _client(kind="platform_admin")
    assert admin.get("/api/v1/platform/model-providers").status_code == 200
    added = admin.post(
        "/api/v1/platform/model-providers",
        json={"name": "platform-fake", "kind": "fake", "baseUrl": "http://127.0.0.1:8099/v1"},
    )
    assert added.status_code == 200
    denied = client.get("/api/v1/platform/model-providers")
    assert denied.status_code == 403
