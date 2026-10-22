"""Edge paths for channel tokens, posts, routing and the channels process."""

import os
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from ar_channels.main import create_application
from ar_channels.render import adaptive_card, approval_blocks, render_email_html
from ar_channels.slack import action_value, command_text, mention_text, should_ignore
from ar_channels.teams import welcome_or_message
from ar_common.errors import NotFoundError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.channels.book import ChannelBook
from ar_domain.channels.posts import (
    load_credentials,
    policy_decision,
    record_channel_post,
    tool_for,
)
from ar_domain.channels.service import decide_approval, handle_inbound
from ar_domain.channels.tokens import issue_link_token, link_ttl_s, read_link_token
from ar_domain.channels.widget_auth import sign_widget_token, verify_widget_token, widget_user
from ar_domain.chat.service import ChatService, demo_id


def _store() -> ChatService:
    store = ChatService()
    store.seed_demo()
    store.seed_showcase()
    return store


def _signed(payload: object) -> str:
    import hashlib
    import hmac

    import orjson

    from ar_domain.channels.tokens import _secret

    body = orjson.dumps(payload)
    digest = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    return f"{body.hex()}.{digest}"


def test_link_tokens_and_widget_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_CHANNEL_LINK_TTL_S", "nope")
    assert link_ttl_s() == 900
    monkeypatch.setenv("AR_CHANNEL_LINK_TTL_S", "30")
    assert link_ttl_s() == 30
    assert read_link_token("not-a-token") is None
    assert read_link_token("zz.not-hex") is None
    forged = issue_link_token(str(demo_id("channel-slack")), "U-1")
    body, _, _digest = forged.partition(".")
    assert read_link_token(f"{body}.{'0' * 64}") is None
    assert read_link_token(_signed(["nope"])) is None
    assert read_link_token(_signed({"exp": "2000-01-01T00:00:00+00:00"})) is None
    blank = _signed({"integration_id": "", "external_user_id": "", "exp": "2999"})
    assert read_link_token(blank) is None
    expired = sign_widget_token(
        secret="s",  # noqa: S106
        audience="aud",
        email="admin@dev.local",
        name="A",
        exp=1,
    )
    assert verify_widget_token(expired, "s", "aud") is None
    assert verify_widget_token("a.b", "s", "aud") is None
    assert verify_widget_token("a.b.c", "s", "aud") is None
    store = ChatService()
    assert widget_user(store, demo_id("tenant"), "stranger@example.com") is None
    assert widget_user(store, demo_id("tenant"), "member@dev.local") == demo_id("member")
    store.user_emails = {demo_id("builder"): "Builder@dev.local"}
    assert widget_user(store, demo_id("tenant"), "builder@dev.local") == demo_id("builder")


def test_posts_credentials_and_closed_agent() -> None:
    store = _store()
    bare = type("Bare", (), {})()
    saved = record_channel_post(bare, tenant_id="t", kind="webhook", body="x", direction="inbound")
    assert saved["external_message_id"]
    assert tool_for("pager") == "delivery.webhook_post"
    assert policy_decision(store, "not-a-uuid", "delivery.slack_post") == "allow"
    store.policies = []
    assert policy_decision(store, demo_id("tenant"), "delivery.slack_post") == "allow"
    assert load_credentials(type("Empty", (), {})(), {}) == {}
    store.secret_values[demo_id("channel-slack")] = b""
    assert load_credentials(store, {"id": demo_id("channel-slack")}) == {}
    store.secret_values[demo_id("channel-slack")] = b"[]"
    assert load_credentials(store, {"id": demo_id("channel-slack")}) == {}
    closed = handle_inbound(
        store,
        {
            "integration_id": demo_id("channel-slack"),
            "kind": "widget",
            "external_user_id": "U-ADMIN",
            "text": "hello",
        },
        schedule=False,
    )
    assert closed["action"] == "no_agent"
    with pytest.raises(NotFoundError):
        decide_approval(store, {"approval_id": uuid.uuid4(), "decision": "approve"})
    book = ChannelBook(store)
    with pytest.raises(NotFoundError):
        book.outbound({"integration_id": None, "text_markdown": "x"})
    with pytest.raises(NotFoundError):
        book.patch(_actor_missing(), demo_id("channel-slack"), {"name": "nope"})
    with pytest.raises(ValidationFailedError):
        book.create(_admin(), {"kind": "pager", "name": "Ops"})
    with pytest.raises(ValidationFailedError):
        book.create(_admin(), {"kind": "slack", "name": " "})
    with pytest.raises(ValidationFailedError):
        book.link(_admin(), "not-a-code")
    store.domain_events = []
    named = book.create(
        _admin(),
        {"kind": "slack", "name": "Events Slack", "credentials": {"bot_token": "xoxb-events"}},
    )
    assert store.domain_events
    assert named["name"] == "Events Slack"
    from ar_domain.channels.showcase import _open_assistant

    class _Copy:
        def model_copy(self, *, update: dict[str, object]) -> dict[str, object]:
            return update

    class _Definition:
        channels = _Copy()

        def model_copy(self, *, update: dict[str, object]) -> dict[str, object]:
            return update

    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()
    store.versions[version_id] = {"definition": _Definition()}
    _open_assistant(store, {"published_version_id": version_id})
    assert store.versions[version_id]["definition"]["channels"]["slack"] is True
    _open_assistant(store, {"published_version_id": agent_id})


def _admin() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=frozenset({"channels:manage", "chat:use"}),
    )


def _actor_missing() -> Actor:
    return Actor(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        permissions=frozenset({"channels:manage"}),
    )


def test_render_and_activity_helpers() -> None:
    assert command_text("") == ("", "")
    assert command_text("/ask only") == ("", "/ask only")
    assert mention_text("<@BOT no-end") == "<@BOT no-end"
    assert should_ignore({"bot_id": "B"}, allowed=[]) == "ignore"
    assert should_ignore({"channel": "C9", "type": "message"}, allowed=["C1"]) == (
        "channel_not_allowed"
    )
    assert should_ignore({"type": "message", "channel_type": "channel"}, allowed=[]) == "ignore"
    assert action_value('{"decision": "approve"}')["decision"] == "approve"
    assert action_value("nope") == {}
    assert approval_blocks("a", "h", step_up=True, web_url="/approvals")[0]["text"] == "Open in web"
    card = adaptive_card("hi", approval_id="a", args_hash="h")
    assert card["actions"]
    stepped = adaptive_card("hi", step_up=True)
    assert stepped["actions"]
    assert "<script>" not in render_email_html("hello <script>bad()</script> onclick=x")
    welcome = welcome_or_message({"type": "conversationUpdate", "text": ""})
    assert welcome["action"] == "welcome"
    ignored = welcome_or_message({"type": "typing"})
    assert ignored["action"] == "ignore"
    invoked = welcome_or_message({"type": "invoke", "text": "approve"})
    assert invoked["action"] == "invoke"


def test_channels_internal_routes_and_bridge_edges() -> None:
    app = create_application()
    client = TestClient(app)
    outbound = client.post("/internal/v1/outbound", json={"text": "hi"})
    assert outbound.json()["external_message_id"] == "out-1"
    notified = client.post("/internal/v1/notify", json={"title": "n"})
    assert notified.json()["delivered"] == ["slack"]
    probed = client.post("/internal/v1/integrations/abc:test")
    assert probed.json()["ok"] is True

    def get(url: str, **kwargs: object) -> httpx.Response:
        del kwargs
        return httpx.Response(200, json=["nope"], request=httpx.Request("GET", url))

    original = httpx.get
    httpx.get = get  # type: ignore[assignment]
    try:
        reloaded = client.post("/internal/v1/integrations:reload")
    finally:
        httpx.get = original
    assert reloaded.json()["count"] == 0

    def down(url: str, **kwargs: object) -> httpx.Response:
        del url, kwargs
        raise httpx.ConnectError("down")

    httpx.get = down  # type: ignore[assignment]
    try:
        from ar_channels.bridge import HttpBridge

        assert HttpBridge("http://api").integrations() == []
        assert HttpBridge("http://api").get("/x") == {}
    finally:
        httpx.get = original
    os.environ.pop("AR_CHANNEL_LINK_TTL_S", None)
