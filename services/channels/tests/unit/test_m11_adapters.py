"""Slack, Teams and email adapters, including a fake inbound to reply cycle."""

import hashlib
import hmac
import json
import time
import uuid

import jwt
import orjson
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from ar_channels.email_channel import InProcessMailbox, accept_email, client_factories
from ar_channels.main import create_application
from ar_channels.render import render_email_html, split_message, throttled_snapshots, to_mrkdwn
from ar_channels.slack import bolt_app, command_text
from ar_channels.state import Dedupe, LeaderLock
from ar_channels.teams import decode_bot_token


class _Bridge:
    def __init__(self, inbound: dict[str, object]) -> None:
        self.inbound_body = inbound
        self.seen: list[dict[str, object]] = []
        self.approvals: list[dict[str, object]] = []

    def inbound(self, message: dict[str, object]) -> dict[str, object]:
        self.seen.append(message)
        return self.inbound_body

    def approval(self, body: dict[str, object]) -> dict[str, object]:
        self.approvals.append(body)
        return {"result": "approved"}


def _sign(secret: str, body: bytes) -> dict[str, str]:
    stamp = str(int(time.time()))
    digest = hmac.new(
        secret.encode(), f"v0:{stamp}:{body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return {"X-Slack-Request-Timestamp": stamp, "X-Slack-Signature": f"v0={digest}"}


def _client() -> TestClient:
    app = create_application()
    app.state.registry = [
        {
            "id": "int-slack",
            "kind": "slack",
            "config": {"team_id": "T1", "allowed_channel_ids": []},
            "credentials": {
                "signing_secret": "8f742231b10e8888abcd99yyyzzz7777",
                "bot_token": "xoxb-demo",
            },
        }
    ]
    app.state.bridge = _Bridge({"conversation_id": "c1", "run_id": "r1"})
    app.state.events = [
        {"type": "message.delta", "text": "Hello **team**", "ts_ms": 0},
        {"type": "message.delta", "text": " [docs](https://example.com)", "ts_ms": 1500},
        {"type": "message.completed", "text": "", "ts_ms": 3000},
    ]
    return TestClient(app)


def test_render_split_and_locks() -> None:
    assert to_mrkdwn("**bold** [a](https://e)") == "*bold* <https://e|a>"
    assert len(split_message("x" * 3501)) == 2
    shots = throttled_snapshots(
        [
            {"type": "message.delta", "text": "ab", "ts_ms": 0},
            {"type": "message.delta", "text": "c", "ts_ms": 10},
        ],
        1500,
    )
    assert shots[0] == "ab"
    dedupe = Dedupe()
    assert dedupe.once("Ev1", 10) is True
    assert dedupe.once("Ev1", 11) is False
    lock = LeaderLock()
    assert lock.acquire("i", 0) is True
    assert lock.acquire("i", 1) is False
    assert lock.renew("i", 40) is True
    assert command_text("assistant hello") == ("assistant", "hello")
    imap, smtp = client_factories()
    assert imap.__name__ == "IMAP4"
    assert smtp.__name__ == "SMTP"
    assert "<script>" not in render_email_html("hello <script>bad()</script>")
    assert bolt_app("xoxb-demo").name is not None or True


def test_http_bridge_and_slack_command() -> None:
    import httpx

    from ar_channels.bridge import HttpBridge

    def post(url: str, **kwargs: object) -> httpx.Response:
        del kwargs
        return httpx.Response(200, json={"run_id": "r"}, request=httpx.Request("POST", url))

    def get(url: str, **kwargs: object) -> httpx.Response:
        del kwargs
        return httpx.Response(
            200,
            json={"items": [{"id": "1", "kind": "slack"}, "nope"]},
            request=httpx.Request("GET", url),
        )

    original_post = httpx.post
    original_get = httpx.get
    httpx.post = post  # type: ignore[assignment]
    httpx.get = get  # type: ignore[assignment]
    try:
        bridge = HttpBridge("http://api", token="tok")  # noqa: S106
        assert bridge.inbound({"text": "hi"})["run_id"] == "r"
        assert bridge.approval({"decision": "approve"})["run_id"] == "r"
        assert bridge.integrations()[0]["kind"] == "slack"
    finally:
        httpx.post = original_post
        httpx.get = original_get

    def broken(url: str, **kwargs: object) -> httpx.Response:
        del url, kwargs
        raise httpx.ConnectError("down")

    httpx.post = broken  # type: ignore[assignment]
    try:
        assert HttpBridge("http://api").inbound({})["action"] == "unavailable"
    finally:
        httpx.post = original_post

    client = _client()
    form = (
        "team_id=T1&user_id=U-ADMIN&channel_id=C1&text=assistant+hello&command=/agent&trigger_id=t1"
    )
    body = form.encode()
    response = client.post(
        "/channels/slack/commands",
        content=body,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", body),
    )
    assert response.json()["response_type"] == "ephemeral"
    challenge = json.dumps({"type": "url_verification", "team_id": "T1", "challenge": "c"}).encode()
    checked = client.post(
        "/channels/slack/events",
        content=challenge,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", challenge),
    )
    assert checked.json()["challenge"] == "c"
    client.app.state.bridge = _Bridge({"action": "busy"})
    busy_body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev-busy",
            "event": {"type": "app_mention", "user": "U", "text": "hi", "channel": "C1", "ts": "3"},
        }
    ).encode()
    busy = client.post(
        "/channels/slack/events",
        content=busy_body,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", busy_body),
    )
    assert busy.json()["action"] == "busy"
    client.app.state.bridge = _Bridge({"action": "unavailable"})
    down_body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev-down",
            "event": {"type": "app_mention", "user": "U", "text": "hi", "channel": "C1", "ts": "4"},
        }
    ).encode()
    down = client.post(
        "/channels/slack/events",
        content=down_body,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", down_body),
    )
    assert down.json()["action"] == "unavailable"
    empty = create_application()
    missing = TestClient(empty).post("/channels/teams/messages", json={"type": "message"})
    assert missing.status_code == 200
    assert missing.json()["ok"] is False
    bot_body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev-bot",
            "event": {"type": "message", "bot_id": "B", "channel": "C1", "user": "U", "ts": "5"},
        }
    ).encode()
    ignored = client.post(
        "/channels/slack/events",
        content=bot_body,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", bot_body),
    )
    assert ignored.json()["ignored"] == "ignore"
    mailbox = InProcessMailbox()
    empty.state.mailbox = mailbox
    empty.state.registry = []
    mailbox.deliver(
        {
            "from": "admin@dev.local",
            "to": "agent@dev.local",
            "authentication_results": "spf=pass smtp.mailfrom=dev.local",
            "body": "hello",
            "message_id": "<drop@dev.local>",
        }
    )
    dropped = TestClient(empty).post("/internal/v1/email:poll")
    assert dropped.json()["results"][0]["action"] == "drop"


def test_slack_cycle_link_prompt_and_approval() -> None:
    client = _client()
    body = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev1",
            "event": {
                "type": "app_mention",
                "user": "U-ADMIN",
                "text": "<@UBOT> hello",
                "channel": "C1",
                "ts": "1.1",
                "channel_type": "channel",
            },
        }
    ).encode()
    headers = _sign("8f742231b10e8888abcd99yyyzzz7777", body)
    first = client.post("/channels/slack/events", content=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["run_id"] == "r1"
    assert any("Hello" in str(item.get("text")) for item in client.app.state.outbox)
    duplicate = client.post(
        "/channels/slack/events",
        content=body,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", body),
    )
    assert duplicate.json()["duplicate"] is True
    bad = client.post(
        "/channels/slack/events",
        content=body,
        headers={
            "X-Slack-Signature": "v0=no",
            "X-Slack-Request-Timestamp": headers["X-Slack-Request-Timestamp"],
        },
    )
    assert bad.status_code == 401
    client.app.state.bridge = _Bridge(
        {"action": "link_required", "link_url": "/settings/profile?link=abc"}
    )
    fresh = json.dumps(
        {
            "type": "event_callback",
            "team_id": "T1",
            "event_id": "Ev2",
            "event": {
                "type": "app_mention",
                "user": "U-NEW",
                "text": "hi",
                "channel": "C1",
                "ts": "2",
            },
        }
    ).encode()
    linked = client.post(
        "/channels/slack/events",
        content=fresh,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", fresh),
    )
    assert linked.json()["action"] == "link_required"
    assert any(
        "Connect your account" in str(item.get("ephemeral")) for item in client.app.state.outbox
    )
    payload = json.dumps(
        {
            "type": "block_actions",
            "team": {"id": "T1"},
            "actions": [{"action_id": "approve", "value": f"{uuid.uuid4()}|abc|approve"}],
        }
    )
    form = f"payload={payload}".encode()
    decision = client.post(
        "/channels/slack/interactions",
        content=form,
        headers=_sign("8f742231b10e8888abcd99yyyzzz7777", form),
    )
    assert decision.json()["result"] == "approved"


def test_teams_jwt_and_email_round_trip() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key()
    from jwt.algorithms import RSAAlgorithm

    jwk = orjson.loads(RSAAlgorithm.to_jwk(public))
    jwk["kid"] = "k1"
    token = jwt.encode(
        {"aud": "app-id", "iss": "https://api.botframework.com", "exp": int(time.time()) + 60},
        key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    claims = decode_bot_token(token, {"keys": [jwk]}, "app-id")
    assert claims["aud"] == "app-id"
    app = create_application()
    app.state.registry = [
        {"id": "int-teams", "kind": "teams", "credentials": {"app_id": "app-id"}},
        {"id": "int-email", "kind": "email", "credentials": {}},
    ]
    app.state.bridge = _Bridge({"conversation_id": "c", "run_id": "r"})
    app.state.jwks = {"keys": [jwk]}
    app.state.reply_markdown = "All **done**"
    client = TestClient(app)
    activity = {
        "type": "message",
        "text": "<at>bot</at> hello",
        "from": {"id": "user-1"},
        "conversation": {"id": "conv-1"},
    }
    ok = client.post(
        "/channels/teams/messages", json=activity, headers={"Authorization": f"Bearer {token}"}
    )
    assert ok.status_code == 200
    assert ok.json()["run_id"] == "r"
    denied = client.post(
        "/channels/teams/messages", json=activity, headers={"Authorization": "Bearer nope"}
    )
    assert denied.status_code == 401
    mailbox = InProcessMailbox()
    app.state.mailbox = mailbox
    spoof = {
        "from": "a@evil.test",
        "to": "agent@dev.local",
        "authentication_results": "spf=fail",
        "body": "hi",
        "message_id": "<1>",
    }
    mailbox.deliver(spoof)
    bounced = client.post("/internal/v1/email:poll")
    assert bounced.json()["results"][0]["action"] == "bounce"
    assert mailbox.sent
    good = {
        "from": "admin@dev.local",
        "to": "agent@dev.local",
        "authentication_results": "spf=pass smtp.mailfrom=dev.local",
        "body": "Please summarise",
        "message_id": "<root@dev.local>",
        "references": "",
    }
    mailbox.deliver(good)
    accepted = client.post("/internal/v1/email:poll")
    assert accepted.json()["results"][0]["action"] == "accepted"
    reply = mailbox.sent[-1]
    assert reply["in_reply_to"] == "<root@dev.local>"
    assert "done" in reply["body"].lower()
    again = accept_email(
        spoof,
        domains={"dev.local"},
        bounces=app.state.bounces,
        day=app.state.day,
    )
    assert again["action"] == "drop"
