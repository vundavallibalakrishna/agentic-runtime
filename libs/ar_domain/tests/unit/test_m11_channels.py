"""Channel catalogue, inbound routing, durable posts and widget tokens."""

import uuid

import pytest

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.channels import tables as channel_tables
from ar_domain.channels.book import ChannelBook, _probe
from ar_domain.channels.manifest import slack_manifest, teams_package
from ar_domain.channels.service import decide_approval, handle_inbound
from ar_domain.channels.tokens import issue_link_token, read_link_token
from ar_domain.channels.widget_auth import sign_widget_token, verify_widget_token
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.flush import _channel_identities, _channel_integrations, _channel_posts
from ar_domain.durable.hydrate import _channel_posts as hydrate_posts
from ar_domain.routines.engine import deliver


def _store() -> ChatService:
    store = ChatService()
    store.seed_demo()
    store.seed_showcase()
    return store


def _actor(user: str = "admin") -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id(user),
        permissions=frozenset({"channels:manage", "chat:use"}),
        display_name=user,
    )


def test_models_import() -> None:
    assert channel_tables.ChannelIntegration.__tablename__ == "channel_integrations"
    assert channel_tables.ChannelPost.__tablename__ == "channel_posts"


def test_showcase_slack_and_recent_post() -> None:
    store = _store()
    book = ChannelBook(store)
    rows = book.list_integrations(_actor())
    assert rows[0]["name"] == "Workspace Slack"
    assert "bot_token" not in rows[0]
    detail = book.get(_actor(), demo_id("channel-slack"))
    posts = detail["recent_posts"]
    assert isinstance(posts, list)
    assert "weekly digest" in str(posts[0]["body"]).lower()
    other = Actor(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset())
    with pytest.raises(NotFoundError):
        book.get(other, demo_id("channel-slack"))


def test_create_test_manifest_and_plan_gate() -> None:
    store = _store()
    book = ChannelBook(store)
    created = book.create(
        _actor(),
        {
            "kind": "slack",
            "name": "Ops Slack",
            "credentials": {"bot_token": "xoxb-ops", "signing_secret": "sec"},
            "config": {"command": "/ask"},
        },
    )
    probed = book.test(_actor(), uuid.UUID(str(created["id"])))
    assert probed["ok"] is True
    media, body, name = book.manifest(_actor(), uuid.UUID(str(created["id"])))
    assert media == "application/yaml"
    assert name == "slack-app.yaml"
    assert b"app_mentions:read" in body
    assert b"signing_secret" not in body
    with pytest.raises(ConflictError):
        book.create(_actor(), {"kind": "slack", "name": "Ops Slack"})
    with pytest.raises(ForbiddenError):
        book.create(
            _actor(), {"kind": "widget", "name": "Portal", "credentials": {"widget_secret": "s"}}
        )
    yaml_text = slack_manifest("Ops", "http://localhost:3000", "/ask")
    assert "commands" in yaml_text
    package = teams_package("Ops", "app-id")
    assert package[:2] == b"PK"


def test_link_identity_and_outbound_policy() -> None:
    store = _store()
    book = ChannelBook(store)
    token = issue_link_token(str(demo_id("channel-slack")), "U-NEW")
    assert read_link_token(token)["external_user_id"] == "U-NEW"
    linked = book.link(_actor("member"), token)
    assert linked["match_method"] == "manual_link"
    mine = book.my_identities(_actor("member"))
    assert any(row["external_user_id"] == "U-NEW" for row in mine)
    waiting = book.outbound(
        {"integration_id": demo_id("channel-slack"), "text_markdown": "hi", "approved": False}
    )
    assert waiting["result"] == "waiting"
    posted = book.outbound(
        {"integration_id": demo_id("channel-slack"), "text_markdown": "hi", "approved": True}
    )
    assert posted["result"] == "posted"
    book.unlink_mine(_actor("member"), uuid.UUID(str(linked["id"])))
    assert book.my_identities(_actor("member")) == []


def test_inbound_known_user_unknown_user_and_approval() -> None:
    store = _store()
    integration = demo_id("channel-slack")
    accepted = handle_inbound(
        store,
        {
            "integration_id": integration,
            "kind": "slack",
            "external_user_id": "U-ADMIN",
            "external_channel_id": "C-PLATFORM",
            "external_thread_id": "1.1",
            "text": "status please",
        },
        schedule=False,
    )
    assert accepted["run_id"]
    link = handle_inbound(
        store,
        {
            "integration_id": integration,
            "kind": "slack",
            "external_user_id": "U-STRANGER",
            "text": "hello",
        },
        schedule=False,
    )
    assert link["action"] == "link_required"
    assert "/settings/profile?link=" in str(link["link_url"])
    conversation_id = uuid.UUID(str(accepted["conversation_id"]))
    conversation = store.conversations[conversation_id]
    run_id = uuid.uuid4()
    store.runs[run_id] = {"id": run_id, "status": "running"}
    conversation["active_run_id"] = run_id
    busy = handle_inbound(
        store,
        {
            "integration_id": integration,
            "kind": "slack",
            "external_user_id": "U-ADMIN",
            "external_channel_id": "C-PLATFORM",
            "external_thread_id": "1.1",
            "text": "again",
        },
        schedule=False,
    )
    assert busy["detail"] == "Still working on the previous request"
    approval_id = uuid.uuid4()
    store.approvals[approval_id] = {"id": approval_id, "status": "pending", "args_hash": "abc"}
    mismatch = decide_approval(
        store, {"approval_id": approval_id, "decision": "approve", "args_hash": "nope"}
    )
    assert mismatch["result"] == "args_mismatch"
    decided = decide_approval(
        store, {"approval_id": approval_id, "decision": "approve", "args_hash": "abc"}
    )
    assert decided["result"] == "approved"


def test_routine_delivery_writes_a_durable_post_and_deny_blocks() -> None:
    store = _store()
    tenant = demo_id("tenant")
    routine_id = uuid.uuid4()
    routine = {
        "id": routine_id,
        "tenant_id": tenant,
        "delivery": [{"type": "slack", "channel": "#platform", "pre_approved": True}],
    }
    store.routines[routine_id] = routine
    outcomes = deliver(store, routine, {"id": uuid.uuid4()}, {"result_summary": "Digest ready"})
    assert outcomes[0]["result"] == "posted"
    assert any(row.get("body") == "Digest ready" for row in store.channel_posts.values())
    policy_id = uuid.uuid4()
    version_id = uuid.uuid4()
    store.policies[policy_id] = {
        "id": policy_id,
        "tenant_id": tenant,
        "status": "active",
        "active_version_id": version_id,
        "name": "block slack",
        "priority": 1,
    }
    store.policy_versions[version_id] = {
        "id": version_id,
        "document": {
            "rules": [
                {
                    "id": "deny-slack",
                    "effect": "deny",
                    "match": {"tools": ["delivery.slack_post"]},
                    "message": "no",
                }
            ]
        },
    }
    denied = deliver(store, routine, {"id": uuid.uuid4()}, {"result_summary": "nope"})
    assert denied[0]["result"] == "denied"


def test_admin_catalogue_patch_delete_and_probes() -> None:
    store = _store()
    book = ChannelBook(store)
    actor = _actor()
    created = book.create(
        actor,
        {
            "kind": "teams",
            "name": "Desk Teams",
            "credentials": {"app_id": "app", "app_password": "pw"},
        },
    )
    integration_id = uuid.UUID(str(created["id"]))
    patched = book.patch(
        actor,
        integration_id,
        {"name": "Desk Teams 2", "status": "disabled", "config": {"command": "/ask"}},
    )
    assert patched["name"] == "Desk Teams 2"
    assert patched["status"] == "disabled"
    probed = book.test(actor, integration_id)
    assert probed["detail"] == "bot token acquired"
    email = book.create(
        actor,
        {"kind": "email", "name": "Desk Mail", "credentials": {"username": "a", "password": "b"}},
    )
    assert book.test(actor, uuid.UUID(str(email["id"])))["ok"] is True
    assert _probe("widget", {}) == (False, "widget secret is missing")
    assert _probe("widget", {"secret": "s"})[0] is True
    assert _probe("slack", {"bot_token": "nope"})[0] is False
    assert _probe("teams", {})[0] is False
    assert _probe("email", {})[0] is False
    rows = book.identities(actor, demo_id("channel-slack"))
    assert rows
    book.delete_identity(actor, demo_id("channel-slack"), uuid.UUID(str(rows[0]["id"])))
    assert book.identities(actor, demo_id("channel-slack")) == []
    token = issue_link_token(str(demo_id("channel-slack")), "U-AGAIN")
    linked = book.link(actor, token)
    again = book.link(actor, token)
    assert again["id"] == linked["id"]
    with pytest.raises(ConflictError):
        book.create(actor, {"kind": "slack", "name": "Workspace Slack"})
    with pytest.raises(NotFoundError):
        book.delete(actor, uuid.uuid4())
    book.delete(actor, integration_id)
    assert all(row["name"] != "Desk Teams 2" for row in book.list_integrations(actor))
    internal = book.integrations_for_channels()
    assert any("credentials" in row for row in internal)
    sent = book.notify(
        {
            "user_id": str(demo_id("admin")),
            "title": "Approval",
            "body_markdown": "Please review",
        }
    )
    assert "slack" in sent["delivered"] or "email" in sent["delivered"]


def test_email_match_command_routing_and_unknown_integration() -> None:
    store = _store()
    integration = demo_id("channel-slack")
    matched = handle_inbound(
        store,
        {
            "integration_id": integration,
            "kind": "email",
            "external_user_id": "admin@dev.local",
            "external_user_email": "admin@dev.local",
            "text": "from mail",
        },
        schedule=False,
    )
    assert matched["run_id"]
    routed = handle_inbound(
        store,
        {
            "integration_id": integration,
            "kind": "slack",
            "external_user_id": "U-ADMIN",
            "text": "status please",
            "command": {"agent_slug": "assistant"},
            "external_thread_id": "cmd-1",
        },
        schedule=False,
    )
    assert routed["run_id"]
    with pytest.raises(NotFoundError):
        handle_inbound(store, {"integration_id": uuid.uuid4(), "text": "nope"}, schedule=False)
    pending = uuid.uuid4()
    store.approvals[pending] = {"id": pending, "status": "pending", "args_hash": ""}
    ignored = decide_approval(store, {"approval_id": pending, "decision": "later"})
    assert ignored["result"] == "ignored"


def test_widget_token_and_notify_fallback() -> None:
    secret = "widget-secret"  # noqa: S105
    audience = "ar-widget:abc"
    exp = int(utcnow().timestamp()) + 60
    token = sign_widget_token(
        secret=secret, audience=audience, email="admin@dev.local", name="Ada", exp=exp
    )
    assert verify_widget_token(token, secret, audience)["sub"] == "admin@dev.local"
    assert verify_widget_token(token, "other", audience) is None
    store = _store()
    for row in list(store.channel_identities):
        store.channel_identities.pop(row, None)
    sent = ChannelBook(store).notify(
        {"user_id": str(demo_id("admin")), "title": "Approval", "body_markdown": "Please review"}
    )
    assert sent["delivered"] == ["email"]


class _Nested:
    async def __aenter__(self) -> _Nested:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


class _Session:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def begin_nested(self) -> _Nested:
        return _Nested()

    async def execute(self, statement: object, params: dict[str, object]) -> object:
        del statement
        self.calls.append(params)
        return self

    def mappings(self) -> list[dict[str, object]]:
        return [{"id": demo_id("channel-slack"), "body": "kept", "tenant_id": demo_id("tenant")}]


@pytest.mark.asyncio
async def test_flush_and_hydrate_channel_rows() -> None:
    session = _Session()
    tenant = demo_id("tenant")
    integration = demo_id("channel-slack")
    await _channel_integrations(
        session,  # type: ignore[arg-type]
        [{"id": integration, "tenant_id": tenant, "kind": "slack", "name": "Workspace Slack"}],
        ChatService(),
    )
    await _channel_identities(session, [{"id": "not-a-uuid"}])  # type: ignore[arg-type]
    await _channel_posts(
        session,  # type: ignore[arg-type]
        [{"id": uuid.uuid4(), "tenant_id": tenant, "kind": "slack", "body": "kept"}],
    )
    assert session.calls
    store = ChatService()
    await hydrate_posts(session, store, tenant)  # type: ignore[arg-type]
    assert store.channel_posts
