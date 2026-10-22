"""Routines HTTP surface, webhook dedupe and cross-tenant 404."""

import hashlib
import hmac
import time
import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS, SYSTEM_ROLE_PERMISSIONS


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


def _sign(secret: str, body: bytes) -> str:
    stamp = int(time.time())
    digest = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={digest}"


def test_routines_round_trip_and_hide_other_tenants() -> None:
    holder: dict[str, Principal | None] = {"principal": _principal()}
    admin = _app(holder)
    listed = admin.get("/api/v1/routines")
    assert listed.status_code == 200
    weekly = next(row for row in listed.json()["items"] if row["name"] == "Weekly digest")
    assert weekly["triggerSummary"] == "Every Monday 09:00 IST"
    detail = admin.get(f"/api/v1/routines/{weekly['id']}")
    assert detail.status_code == 200
    assert "webhookSecret" not in detail.json()
    assert len(detail.json()["nextFires"]) == 5
    agents = admin.get("/api/v1/agents")
    agent_id = agents.json()["items"][0]["id"]
    created = admin.post(
        "/api/v1/routines",
        json={
            "name": "Launch reminder",
            "agentId": agent_id,
            "instructions": "Remind the team.",
            "trigger": {"type": "webhook"},
            "delivery": [{"type": "conversation"}],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["webhook"]["webhookSecret"]
    secret = body["webhook"]["webhookSecret"]
    token = body["webhook"]["webhookUrl"].rsplit("/", 1)[-1]
    preview = admin.post(
        "/api/v1/routines:preview-schedule",
        json={"cron": "0 9 * * 1", "timezone": "Asia/Kolkata"},
    )
    assert preview.status_code == 200
    assert preview.json()["valid"] is True
    ran = admin.post(f"/api/v1/routines/{body['id']}:run", json={"input": "now", "test": True})
    assert ran.status_code == 202
    assert ran.json()["runId"]
    paused = admin.post(f"/api/v1/routines/{body['id']}:pause")
    assert paused.json()["status"] == "paused"
    resumed = admin.post(f"/api/v1/routines/{body['id']}:resume")
    assert resumed.json()["status"] == "active"
    rotated = admin.post(f"/api/v1/routines/{body['id']}:rotate-webhook-secret")
    assert rotated.status_code == 200
    assert rotated.json()["webhookSecret"] != secret
    holder["principal"] = _principal(tenant=uuid.uuid4())
    hidden = admin.get(f"/api/v1/routines/{body['id']}")
    assert hidden.status_code == 404
    holder["principal"] = _principal(
        user="member", permissions=frozenset(SYSTEM_ROLE_PERMISSIONS["member"])
    )
    denied = admin.post(
        f"/api/v1/routines/{weekly['id']}:transfer",
        json={"newOwnerUserId": str(demo_id("member"))},
    )
    assert denied.status_code == 403
    holder["principal"] = None
    payload = b'{"ticket":1}'
    bad = admin.post(f"/api/v1/hooks/routines/{token}", content=payload)
    assert bad.status_code == 401
    signed = admin.post(
        f"/api/v1/hooks/routines/{token}",
        content=payload,
        headers={"X-AR-Signature": _sign(rotated.json()["webhookSecret"], payload)},
    )
    assert signed.status_code == 202
    replay = admin.post(
        f"/api/v1/hooks/routines/{token}",
        content=payload,
        headers={"X-AR-Signature": _sign(rotated.json()["webhookSecret"], payload)},
    )
    assert replay.status_code == 409
    assert replay.json()["eventId"] == signed.json()["eventId"]
    missing = admin.post("/api/v1/hooks/routines/no-such-token", content=payload)
    assert missing.status_code == 404
