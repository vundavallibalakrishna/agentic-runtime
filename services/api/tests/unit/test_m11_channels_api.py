"""Channel, OpenAI and widget HTTP surfaces."""

import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from ar_api.main import create_application
from ar_common.time import utcnow
from ar_domain.channels.widget_auth import sign_widget_token
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _principal(
    *,
    tenant: uuid.UUID | None = None,
    user: str = "admin",
    permissions: frozenset[str] | None = None,
) -> Principal:
    return Principal(
        kind="user",
        id=str(demo_id(user)),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email=f"{user}@dev.local",
        display_name=user,
        roles=frozenset({"tenant_admin"}),
    )


def _app(holder: dict[str, Principal | None]) -> TestClient:
    app = create_application()

    async def resolve(scope: object) -> Principal | None:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    app.state.chat.seed_showcase()
    return TestClient(app)


def test_integrations_hide_other_tenants_and_keep_secrets() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    listed = client.get("/api/v1/channel-integrations")
    assert listed.status_code == 200
    slack = next(row for row in listed.json()["items"] if row["name"] == "Workspace Slack")
    assert "botToken" not in slack
    detail = client.get(f"/api/v1/channel-integrations/{slack['id']}")
    assert detail.status_code == 200
    assert detail.json()["recentPosts"]
    manifest = client.get(f"/api/v1/channel-integrations/{slack['id']}/manifest")
    assert manifest.status_code == 200
    assert b"chat:write" in manifest.content
    probed = client.post(f"/api/v1/channel-integrations/{slack['id']}:test")
    assert probed.json()["ok"] is True
    created = client.post(
        "/api/v1/channel-integrations",
        json={"kind": "slack", "name": "Desk Slack", "credentials": {"botToken": "xoxb-desk"}},
    )
    assert created.status_code == 201
    holder["principal"] = _principal(tenant=uuid.uuid4())
    hidden = client.get(f"/api/v1/channel-integrations/{created.json()['id']}")
    assert hidden.status_code == 404
    holder["principal"] = _principal(permissions=frozenset({"chat:use"}))
    forbidden = client.get("/api/v1/channel-integrations")
    assert forbidden.status_code == 403
    identities = client.get("/api/v1/me/channel-identities")
    assert identities.status_code == 200
    assert identities.json()["items"]
    holder["principal"] = _principal()
    slack_id = slack["id"]
    people = client.get(f"/api/v1/channel-integrations/{slack_id}/identities")
    assert people.status_code == 200
    identity_id = people.json()["items"][0]["id"]
    patched = client.patch(
        f"/api/v1/channel-integrations/{slack_id}",
        json={"status": "disabled", "name": "Workspace Slack"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "disabled"
    removed = client.delete(f"/api/v1/me/channel-identities/{identity_id}")
    assert removed.status_code == 204
    gone = client.delete(f"/api/v1/channel-integrations/{created.json()['id']}")
    assert gone.status_code == 204
    approval = uuid.uuid4()
    client.app.state.chat.approvals[approval] = {
        "id": approval,
        "status": "pending",
        "args_hash": "abc",
    }
    decided = client.post(
        "/internal/v1/channels/approval-decisions",
        json={"approvalId": str(approval), "decision": "reject", "argsHash": "abc"},
    )
    assert decided.status_code == 200
    assert decided.json()["result"] == "rejected"
    frame_missing = client.get(f"/api/v1/widget/integrations/{uuid.uuid4()}")
    assert frame_missing.status_code == 404


def test_widget_session_and_frame_ancestors() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    store = client.app.state.chat
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"features": {"widget": True}}
    created = client.post(
        "/api/v1/channel-integrations",
        json={
            "kind": "widget",
            "name": "Portal",
            "credentials": {"widgetSecret": "widget-secret"},
            "config": {"allowedOrigins": ["https://portal.example"]},
        },
    )
    assert created.status_code == 201
    integration_id = created.json()["id"]
    frame = client.get(f"/api/v1/widget/integrations/{integration_id}")
    assert frame.json()["allowedOrigins"] == ["https://portal.example"]
    token = sign_widget_token(
        secret="widget-secret",  # noqa: S106
        audience=f"ar-widget:{integration_id}",
        email="admin@dev.local",
        name="Admin",
        exp=int(utcnow().timestamp()) + 120,
    )
    holder["principal"] = None
    session = client.post(
        "/api/v1/widget/sessions",
        json={"integrationId": integration_id, "token": token},
    )
    assert session.status_code == 204
    assert "ar_widget_session=" in session.headers["set-cookie"]
    rejected = client.post(
        "/api/v1/widget/sessions",
        json={"integrationId": integration_id, "token": "nope"},
    )
    assert rejected.status_code == 401


async def test_inbound_and_openai_sdk_stream() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    integration = str(demo_id("channel-slack"))
    inbound = client.post(
        "/internal/v1/channels/inbound",
        json={
            "integrationId": integration,
            "kind": "slack",
            "externalUserId": "U-ADMIN",
            "externalChannelId": "C-PLATFORM",
            "externalThreadId": "9.1",
            "text": "hello from slack",
        },
    )
    assert inbound.status_code == 200
    assert inbound.json()["runId"]
    transport = httpx.ASGITransport(app=client.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        sdk = AsyncOpenAI(
            api_key="ark_test", base_url="http://test/api/v1/openai", http_client=http_client
        )
        models = await sdk.models.list()
        assert any(model.id == "assistant" for model in models.data)
        with pytest.raises(Exception, match="400"):
            await sdk.chat.completions.create(
                model="assistant",
                messages=[{"role": "user", "content": "hi"}],
                tools=[{"type": "function", "function": {"name": "ping"}}],
            )
        started = time.perf_counter()
        chunks = await sdk.chat.completions.create(
            model="assistant",
            messages=[{"role": "user", "content": "ping the channel"}],
            stream=True,
            user="ignored-user",
        )
        text = "".join([chunk.choices[0].delta.content or "" async for chunk in chunks])
        assert text
        assert time.perf_counter() - started < 30
        plain = await sdk.chat.completions.create(
            model="assistant",
            messages=[{"role": "user", "content": "plain ping"}],
        )
        assert plain.choices[0].message.content
        continued = await sdk.chat.completions.create(
            model="assistant",
            messages=[
                {"role": "user", "content": [{"type": "text", "text": "earlier"}]},
                {"role": "assistant", "content": "noted"},
                {"role": "user", "content": "and now"},
            ],
            extra_headers={"X-AR-Conversation-Id": str(demo_id("showcase-status"))},
        )
        assert continued.choices[0].message.content
        empty = await http_client.post(
            "/api/v1/openai/chat/completions",
            json={"model": "assistant", "messages": [{"role": "system", "content": "only"}]},
        )
        assert empty.status_code == 422
        missing = await http_client.post(
            "/api/v1/openai/chat/completions",
            json={"model": "missing-agent", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert missing.status_code == 404
