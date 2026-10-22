"""Usage and quota HTTP surface."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_common.settings import DeploymentMode
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _principal(
    *,
    tenant: uuid.UUID | None = None,
    user: str = "admin",
    permissions: frozenset[str] | None = None,
    kind: str = "user",
) -> Principal:
    return Principal(
        kind=kind,  # type: ignore[arg-type]
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
    return TestClient(app)


def test_quota_crud_isolation_and_token_block() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    listed = client.get("/api/v1/quotas")
    assert listed.status_code == 200
    seeded = next(row for row in listed.json()["items"] if row["metric"] == "model_tokens")
    assert seeded["limitValue"] == 100_000
    created = client.post(
        "/api/v1/quotas",
        json={
            "scopeType": "tenant",
            "metric": "runs",
            "period": "month",
            "limitValue": 20,
            "action": "warn",
            "warnAtPct": 50,
        },
    )
    assert created.status_code == 201
    quota_id = created.json()["id"]
    duplicate = client.post(
        "/api/v1/quotas",
        json={"scopeType": "tenant", "metric": "runs", "period": "month", "limitValue": 1},
    )
    assert duplicate.status_code == 409
    patched = client.patch(f"/api/v1/quotas/{quota_id}", json={"limitValue": 30})
    assert patched.json()["limitValue"] == 30
    holder["principal"] = _principal(tenant=uuid.uuid4())
    hidden = client.patch(f"/api/v1/quotas/{quota_id}", json={"limitValue": 1})
    assert hidden.status_code == 404
    holder["principal"] = _principal(permissions=frozenset({"chat:use"}))
    forbidden = client.get("/api/v1/quotas")
    assert forbidden.status_code == 403
    holder["principal"] = _principal()
    blocked = client.patch(
        f"/api/v1/quotas/{demo_id('quota-tokens')}",
        json={"limitValue": 10_000},
    )
    assert blocked.status_code == 200
    conversations = client.get("/api/v1/conversations")
    conversation_id = conversations.json()["items"][0]["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "hello"},
    )
    assert posted.status_code == 429
    body = posted.json()
    assert body["code"] == "quota_exceeded"
    assert "10,000" in body["detail"]
    assert "Quota reached" in body["detail"]
    removed = client.delete(f"/api/v1/quotas/{quota_id}")
    assert removed.status_code == 204
    restored = client.patch(
        f"/api/v1/quotas/{demo_id('quota-tokens')}",
        json={"limitValue": 100_000},
    )
    assert restored.status_code == 200


def test_agent_quota_blocks_only_that_agent() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    created = client.post(
        "/api/v1/agents",
        json={"slug": "quota-probe", "name": "Quota probe", "description": "probe"},
    )
    assert created.status_code == 200
    agent_id = created.json()["id"]
    published = client.post(f"/api/v1/agents/{agent_id}:publish", json={"changeNote": "probe"})
    assert published.status_code == 200
    quota = client.post(
        "/api/v1/quotas",
        json={
            "scopeType": "agent",
            "scopeId": agent_id,
            "metric": "model_tokens",
            "period": "day",
            "limitValue": 0,
            "action": "block",
        },
    )
    assert quota.status_code == 201
    opened = client.post("/api/v1/conversations", json={"agentId": agent_id})
    assert opened.status_code == 200
    posted = client.post(
        f"/api/v1/conversations/{opened.json()['id']}/messages",
        json={"text": "hello"},
    )
    assert posted.status_code == 429
    assert posted.json()["code"] == "quota_exceeded"
    assistant = client.post("/api/v1/conversations", json={})
    assert assistant.status_code == 200
    allowed = client.post(
        f"/api/v1/conversations/{assistant.json()['id']}/messages",
        json={"text": "hello"},
    )
    assert allowed.status_code == 202


def test_usage_export_matches_daily_and_platform_is_saas_only() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    summary = client.get("/api/v1/usage/summary", params={"group_by": "day,metric"})
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["currency"] == "INR"
    assert payload["totals"]["quantity"] > 0
    exported = client.get("/api/v1/usage/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    lines = [line for line in exported.text.splitlines() if line]
    assert lines[0].startswith("day,metric,user_email")
    daily = sum(item.quantity for item in client.app.state.chat.usage_daily.values())
    assert sum(int(line.split(",")[6]) for line in lines[1:]) == daily
    mine = client.get("/api/v1/me/usage")
    assert mine.status_code == 200
    assert mine.json()["quotas"]
    missing = client.get("/api/v1/platform/usage")
    assert missing.status_code == 404
    client.app.state.settings.deployment_mode = DeploymentMode.SAAS
    denied = client.get("/api/v1/platform/usage")
    assert denied.status_code == 403
    holder["principal"] = _principal(kind="platform_admin")
    allowed = client.get("/api/v1/platform/usage", params={"group_by": "tenant"})
    assert allowed.status_code == 200
    sheet = client.get("/api/v1/platform/usage/export")
    assert sheet.status_code == 200
    assert sheet.text.splitlines()[0].startswith("tenant_id,day,metric")


def test_agent_cap_is_plan_limit_reached() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    client = _app(holder)
    store = client.app.state.chat
    tenant = demo_id("tenant")
    settings = dict(store.tenant_settings.get(tenant) or {})
    settings["plan_limits"] = {"max_agents": 200}
    store.tenant_settings[tenant] = settings
    existing = sum(1 for row in store.agents.values() if row.get("tenant_id") == tenant)
    for index in range(200 - existing):
        store.agents[uuid.uuid4()] = {"tenant_id": tenant, "slug": f"pad-{index}"}
    created = client.post(
        "/api/v1/agents",
        json={"slug": "one-more-agent", "name": "One more"},
    )
    assert created.status_code == 409
    assert created.json()["code"] == "plan_limit_reached"
    assert created.json()["detail"] == "max_agents"
