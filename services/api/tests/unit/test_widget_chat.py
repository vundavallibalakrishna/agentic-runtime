"""Widget sessions are short lived and cannot escape their integration or conversation."""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from ar_api.auth.session import MemorySessionStore, new_session
from ar_api.main import create_application
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.channels.book import ChannelBook
from ar_domain.channels.widget_auth import sign_widget_token
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS


@pytest.fixture
def widget_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str, str]:
    monkeypatch.setenv("AR_PUBLIC_URL", "https://localhost:3000")
    app = create_application()
    app.state.await_runs = True
    store = app.state.chat
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"features": {"widget": True}}
    actor = Actor(tenant, demo_id("admin"), PERMISSION_KEYS)
    agent_id = next(
        str(agent["id"]) for agent in store.agents.values() if agent["slug"] == "assistant"
    )
    row = ChannelBook(store).create(
        actor,
        {
            "kind": "widget",
            "name": "Portal",
            "default_agent_id": agent_id,
            "credentials": {"widget_secret": "widget-test-secret"},
            "config": {"allowedOrigins": ["https://portal.example"]},
        },
    )
    with TestClient(app, base_url="https://localhost:3000") as client:
        yield client, str(row["id"]), agent_id


def _login(
    client: TestClient, integration_id: str, *, email: str = "admin@dev.local", ttl: int = 120
) -> None:
    token = sign_widget_token(
        secret="widget-test-secret",  # noqa: S106
        audience=f"ar-widget:{integration_id}",
        email=email,
        name="Admin",
        exp=int(utcnow().timestamp()) + ttl,
    )
    response = client.post(
        "/api/v1/widget/sessions", json={"integrationId": integration_id, "token": token}
    )
    assert response.status_code == 204, response.text
    assert all(
        flag in response.headers["set-cookie"]
        for flag in ("HttpOnly", "Secure", "SameSite=None", "Partitioned")
    )


def _headers(client: TestClient) -> dict[str, str]:
    session = client.get("/api/v1/widget/session")
    assert session.status_code == 200, session.text
    return {"x-csrf-token": session.json()["csrfToken"], "origin": "https://localhost:3000"}


def test_widget_streams_and_rejects_unrelated_resources(
    widget_client: tuple[TestClient, str, str],
) -> None:
    client, integration_id, agent_id = widget_client
    _login(client, integration_id)
    context = client.get("/api/v1/widget/session").json()
    assert context["agents"] == [{"id": agent_id, "name": "Assistant"}]
    headers = _headers(client)
    assert client.get("/api/v1/agents").status_code == 401
    assert (
        client.post("/api/v1/widget/conversations", json={"agentId": agent_id}).status_code == 403
    )
    assert (
        client.post(
            "/api/v1/widget/conversations", json={"agentId": str(uuid.uuid4())}, headers=headers
        ).status_code
        == 404
    )
    created = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    )
    assert created.status_code == 200, created.text
    conversation_id = created.json()["id"]
    message = client.post(
        f"/api/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "Hello from the portal"},
        headers=headers,
    )
    assert message.status_code == 202, message.text
    run_id = message.json()["run"]["id"]
    events = client.get(f"/api/v1/widget/runs/{run_id}/events")
    assert events.status_code == 200
    assert "event: run.completed" in events.text
    saved = client.get(f"/api/v1/widget/conversations/{conversation_id}")
    assert any("Hello from the portal" in item["text"] for item in saved.json()["messages"])
    other = client.app.state.chat.create_conversation(
        demo_id("tenant"), demo_id("admin"), uuid.UUID(agent_id)
    )
    assert client.get(f"/api/v1/widget/conversations/{other['id']}").status_code == 404
    assert client.get(f"/api/v1/widget/runs/{uuid.uuid4()}/events").status_code == 404
    # Rotation revokes the previous session even for the same person and integration.
    _login(client, integration_id)
    assert client.get(f"/api/v1/widget/conversations/{conversation_id}").status_code == 404


def test_widget_expiry_and_revocation(
    widget_client: tuple[TestClient, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, integration_id, _ = widget_client
    _login(client, integration_id, ttl=60)
    now = utcnow()
    monkeypatch.setattr("ar_api.auth.session.utcnow", lambda: now + timedelta(seconds=61))
    assert client.get("/api/v1/widget/session").status_code == 401
    monkeypatch.setattr("ar_api.auth.session.utcnow", lambda: now)
    _login(client, integration_id)
    client.app.state.chat.channel_integrations[uuid.UUID(integration_id)]["status"] = "disabled"
    assert client.get("/api/v1/widget/session").status_code == 404
    assert client.get(f"/api/v1/widget/integrations/{integration_id}").status_code == 404


def test_widget_rejects_unknown_user_and_wrong_tenant(
    widget_client: tuple[TestClient, str, str],
) -> None:
    client, integration_id, _ = widget_client
    token = sign_widget_token(
        secret="widget-test-secret",  # noqa: S106
        audience=f"ar-widget:{integration_id}",
        email="unknown@dev.local",
        name="Unknown",
        exp=int(utcnow().timestamp()) + 120,
    )
    assert (
        client.post(
            "/api/v1/widget/sessions", json={"integrationId": integration_id, "token": token}
        ).status_code
        == 401
    )
    _login(client, integration_id)
    row = client.app.state.chat.channel_integrations[uuid.UUID(integration_id)]
    row["tenant_id"] = uuid.uuid4()
    client.app.state.chat.tenant_settings[row["tenant_id"]] = {"features": {"widget": True}}
    assert client.get("/api/v1/widget/session").status_code == 404


async def test_session_updates_preserve_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    now = utcnow()
    monkeypatch.setattr("ar_api.auth.session.utcnow", lambda: now)
    store = MemorySessionStore(b"x" * 32)
    key, data = new_session(demo_id("tenant"), demo_id("admin"))
    await store.put(key, data, 10)
    monkeypatch.setattr("ar_api.auth.session.utcnow", lambda: now + timedelta(seconds=5))
    data.widget_conversation_id = uuid.uuid4()
    await store.update(key, data)
    assert (await store.get(key)).widget_conversation_id == data.widget_conversation_id
    monkeypatch.setattr("ar_api.auth.session.utcnow", lambda: now + timedelta(seconds=11))
    assert await store.get(key) is None
    await store.update(key, data)
    assert await store.get(key) is None
