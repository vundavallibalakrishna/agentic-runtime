"""Widget sessions are short lived and cannot escape their integration or conversation."""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from ar_api.auth.session import MemorySessionStore, new_session
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.channels.book import ChannelBook
from ar_domain.channels.widget_auth import sign_widget_token
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


@pytest.fixture
def widget_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str, str]:
    monkeypatch.setenv("AR_PUBLIC_URL", "https://localhost:3000")
    app = demo_application()
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


def _open(store: object, agent_id: str, *, public: bool = True) -> None:
    """Let anonymous visitors chat with the agent, as its owner would before publishing."""
    agent = store.agents[uuid.UUID(agent_id)]  # type: ignore[attr-defined]
    version = store.versions[agent["published_version_id"]]  # type: ignore[attr-defined]
    definition = dict(version["definition"])
    definition["channels"] = {**dict(definition.get("channels") or {}), "public": public}
    version["definition"] = definition


@pytest.fixture
def public_widget(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str, str]:
    """A widget anyone may open: visitors act as one account the tenant names."""
    monkeypatch.setenv("AR_PUBLIC_URL", "https://localhost:3000")
    app = demo_application()
    app.state.await_runs = True
    store = app.state.chat
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"features": {"widget": True}}
    actor = Actor(tenant, demo_id("admin"), PERMISSION_KEYS)
    agent_id = next(
        str(agent["id"]) for agent in store.agents.values() if agent["slug"] == "assistant"
    )
    _open(store, agent_id)
    row = ChannelBook(store).create(
        actor,
        {
            "kind": "widget",
            "name": "Website",
            "default_agent_id": agent_id,
            "config": {
                "access": "public",
                "visitorEmail": "admin@dev.local",
                "allowedOrigins": ["https://site.example"],
                "maxMessages": 2,
                "maxMessageChars": 40,
                "sessionsPerClientPerMinute": 3,
                "notice": "Messages are kept to improve answers.",
            },
        },
    )
    with TestClient(app, base_url="https://localhost:3000") as client:
        yield client, str(row["id"]), agent_id


def _visit(client: TestClient, integration_id: str) -> dict[str, str]:
    started = client.post("/api/v1/widget/sessions", json={"integrationId": integration_id})
    assert started.status_code == 204, started.text
    return _headers(client)


def test_a_public_widget_lets_a_visitor_chat_without_signing_in(
    public_widget: tuple[TestClient, str, str],
) -> None:
    client, integration_id, agent_id = public_widget
    frame = client.get(f"/api/v1/widget/integrations/{integration_id}").json()
    assert (frame["access"], frame["notice"]) == ("public", "Messages are kept to improve answers.")
    headers = _visit(client, integration_id)
    context = client.get("/api/v1/widget/session").json()
    assert context["public"] is True
    assert context["agents"] == [{"id": agent_id, "name": "Assistant"}]
    # The session can chat and nothing else: no workspace endpoint takes it.
    assert client.get("/api/v1/agents").status_code == 401
    assert client.get("/api/v1/conversations").status_code == 401
    created = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    )
    conversation_id = created.json()["id"]
    sent = client.post(
        f"/api/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "What do you sell?"},
        headers=headers,
    )
    assert sent.status_code == 202, sent.text
    events = client.get(f"/api/v1/widget/runs/{sent.json()['run']['id']}/events")
    assert "event: run.completed" in events.text


def test_one_visitor_cannot_reach_another_visitors_conversation(
    public_widget: tuple[TestClient, str, str],
) -> None:
    """Every visitor acts as the same account. The session is what keeps them apart."""
    client, integration_id, agent_id = public_widget
    first = _visit(client, integration_id)
    theirs = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=first
    ).json()["id"]
    client.post(
        f"/api/v1/widget/conversations/{theirs}/messages",
        json={"text": "My name is Ada and my number is 555 0100."},
        headers=first,
    )
    # A second visitor: a new session on the same widget.
    client.cookies.clear()
    second = _visit(client, integration_id)
    assert client.get("/api/v1/widget/session").json()["conversationId"] is None
    assert client.get(f"/api/v1/widget/conversations/{theirs}").status_code == 404
    assert (
        client.post(
            f"/api/v1/widget/conversations/{theirs}/messages",
            json={"text": "What did the last person say?"},
            headers=second,
        ).status_code
        == 404
    )


def test_a_public_session_is_bounded_in_what_it_can_send_and_store(
    public_widget: tuple[TestClient, str, str],
) -> None:
    client, integration_id, agent_id = public_widget
    headers = _visit(client, integration_id)
    conversation_id = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    ).json()["id"]
    path = f"/api/v1/widget/conversations/{conversation_id}/messages"
    for text in ("one", "two"):
        assert client.post(path, json={"text": text}, headers=headers).status_code == 202
    third = client.post(path, json={"text": "three"}, headers=headers)
    assert third.status_code == 429
    assert "reached its limit" in third.json()["detail"]
    # A new conversation in the same session does not start the count again.
    again = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    ).json()["id"]
    assert (
        client.post(
            f"/api/v1/widget/conversations/{again}/messages", json={"text": "four"}, headers=headers
        ).status_code
        == 429
    )
    upload = client.post(
        "/api/v1/widget/files",
        files={"upload": ("note.txt", b"hello", "text/plain")},
        headers={key: value for key, value in headers.items() if key != "content-type"},
    )
    assert upload.status_code == 403


def test_one_address_can_start_only_so_many_public_chats_in_a_minute(
    public_widget: tuple[TestClient, str, str],
) -> None:
    client, integration_id, _agent = public_widget
    answers = []
    for _ in range(4):
        client.cookies.clear()
        answers.append(
            client.post("/api/v1/widget/sessions", json={"integrationId": integration_id})
        )
    assert [item.status_code for item in answers] == [204, 204, 204, 429]
    assert answers[-1].headers.get("retry-after")


def test_a_public_widget_needs_an_active_account_for_its_visitors(
    public_widget: tuple[TestClient, str, str],
) -> None:
    client, integration_id, _agent = public_widget
    store = client.app.state.chat
    row = ChannelBook(store)._integrations()[uuid.UUID(integration_id)]
    row["config"] = {**row["config"], "visitorEmail": "nobody@dev.local"}
    assert (
        client.post("/api/v1/widget/sessions", json={"integrationId": integration_id}).status_code
        == 401
    )
    row["config"] = {**row["config"], "visitorEmail": ""}
    assert (
        client.post("/api/v1/widget/sessions", json={"integrationId": integration_id}).status_code
        == 401
    )


def test_testing_a_public_widget_does_not_ask_for_a_host_secret(
    public_widget: tuple[TestClient, str, str],
) -> None:
    client, integration_id, _agent = public_widget
    store = client.app.state.chat
    actor = Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)
    answer = ChannelBook(store).test(actor, uuid.UUID(integration_id))
    assert answer == {"ok": True, "detail": "the visitor account is set"}
    # It is still open to visitors after the test.
    assert (
        client.post("/api/v1/widget/sessions", json={"integrationId": integration_id}).status_code
        == 204
    )


def test_a_widget_that_is_not_public_still_needs_the_hosts_token(
    widget_client: tuple[TestClient, str, str],
) -> None:
    client, integration_id, _agent = widget_client
    frame = client.get(f"/api/v1/widget/integrations/{integration_id}").json()
    assert (frame["access"], frame["notice"]) == ("signed", "")
    assert (
        client.post("/api/v1/widget/sessions", json={"integrationId": integration_id}).status_code
        == 401
    )


def test_a_public_widget_reaches_only_agents_opened_to_visitors(
    public_widget: tuple[TestClient, str, str],
) -> None:
    """Putting an agent behind a public widget is not enough: its owner must open it."""
    client, integration_id, agent_id = public_widget
    _open(client.app.state.chat, agent_id, public=False)
    headers = _visit(client, integration_id)
    assert client.get("/api/v1/widget/session").json()["agents"] == []
    refused = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    )
    assert refused.status_code == 404


def test_a_visitors_message_can_be_only_so_long(
    public_widget: tuple[TestClient, str, str],
) -> None:
    client, integration_id, agent_id = public_widget
    frame = client.get(f"/api/v1/widget/integrations/{integration_id}").json()
    assert frame["maxMessageChars"] == 40
    headers = _visit(client, integration_id)
    conversation_id = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    ).json()["id"]
    long = client.post(
        f"/api/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "x" * 41},
        headers=headers,
    )
    assert long.status_code == 422
    assert "at most 40 characters" in long.json()["detail"]
    # A message that was refused is not one of the session's messages.
    for _ in range(2):
        assert (
            client.post(
                f"/api/v1/widget/conversations/{conversation_id}/messages",
                json={"text": "short"},
                headers=headers,
            ).status_code
            == 202
        )


def test_visitors_behind_the_installs_proxy_are_counted_apart() -> None:
    from ar_domain.channels.widget_auth import client_address

    ours = "127.0.0.0/8,10.0.0.0/8"
    # The web app and an ingress are in front: the visitor is the address they report.
    assert client_address("127.0.0.1", "203.0.113.7, 10.0.0.4", ours) == "203.0.113.7"
    # A caller that is not one of the proxies is itself, whatever it writes in the header.
    assert client_address("198.51.100.9", "203.0.113.7", ours) == "198.51.100.9"
    # A proxy that names nobody, or names nonsense, is counted as itself.
    assert client_address("127.0.0.1", "", ours) == "127.0.0.1"
    assert client_address("127.0.0.1", "not-an-address", ours) == "127.0.0.1"
    # A visitor cannot hide behind an address they added in front of the real one.
    assert client_address("127.0.0.1", "1.2.3.4, 203.0.113.7", ours) == "203.0.113.7"


def _cited_conversation(client: TestClient, integration_id: str, agent_id: str) -> str:
    """A widget conversation whose reply cites one web page."""
    _login(client, integration_id)
    headers = _headers(client)
    conversation_id = client.post(
        "/api/v1/widget/conversations", json={"agentId": agent_id}, headers=headers
    ).json()["id"]
    sent = client.post(
        f"/api/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "Which industries do you serve?"},
        headers=headers,
    )
    assert sent.status_code == 202, sent.text
    client.get(f"/api/v1/widget/runs/{sent.json()['run']['id']}/events")
    store = client.app.state.chat
    reply = next(
        row
        for row in store.messages.values()
        if str(row["conversation_id"]) == conversation_id and row.get("role") == "assistant"
    )
    card = {"index": 1, "title": "Industries", "uri": "https://example.test/industries/"}
    reply["content"] = [
        *(reply.get("content") or []),
        {"type": "citation_ref", "index": 1, "citation": card},
    ]
    return conversation_id


def _parts(client: TestClient, conversation_id: str) -> list[str]:
    saved = client.get(f"/api/v1/widget/conversations/{conversation_id}").json()
    return [
        part.get("type")
        for message in saved["messages"]
        for part in message.get("content") or []
        if isinstance(part, dict)
    ]


def test_a_widget_shows_the_sources_an_answer_cites_unless_turned_off(
    widget_client: tuple[TestClient, str, str],
) -> None:
    client, integration_id, agent_id = widget_client
    conversation_id = _cited_conversation(client, integration_id, agent_id)
    assert "citation_ref" in _parts(client, conversation_id)

    store = client.app.state.chat
    actor = Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)
    ChannelBook(store).patch(
        actor,
        uuid.UUID(integration_id),
        {"config": {"allowedOrigins": ["https://portal.example"], "showSources": False}},
    )
    # The visitor receives no source at all, not one the screen merely hides.
    assert "citation_ref" not in _parts(client, conversation_id)


def test_taking_sources_out_leaves_the_rest_of_each_message() -> None:
    from ar_domain.channels.widget_auth import show_sources, without_sources

    conversation = {
        "id": "c1",
        "messages": [
            {"id": "m1", "text": "Hi", "content": [{"type": "text", "text": "Hi"}]},
            {
                "id": "m2",
                "text": "Banks [1]",
                "content": [
                    {"type": "text", "text": "Banks [1]"},
                    {"type": "citation_ref", "index": 1, "citation": {"title": "Industries"}},
                ],
            },
            {"id": "m3", "text": "No content parts"},
        ],
    }
    stripped = without_sources(conversation)
    assert [m["content"] for m in stripped["messages"][:2]] == [
        [{"type": "text", "text": "Hi"}],
        [{"type": "text", "text": "Banks [1]"}],
    ]
    assert stripped["messages"][2] == {"id": "m3", "text": "No content parts"}
    assert conversation["messages"][1]["content"][1]["type"] == "citation_ref"  # not changed
    assert show_sources({}) is True
    assert show_sources({"showSources": False}) is False
    assert show_sources({"show_sources": False}) is False
    assert show_sources(None) is True
