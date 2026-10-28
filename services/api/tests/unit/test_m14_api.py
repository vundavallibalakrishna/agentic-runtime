"""Assurance HTTP surface."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _principal(
    *,
    tenant: uuid.UUID | None = None,
    permissions: frozenset[str] | None = None,
    kind: str = "user",
    support_level: str | None = None,
    step_up_at: object | None = None,
    user_id: str | None = None,
) -> Principal:
    return Principal(
        kind=kind,  # type: ignore[arg-type]
        id=user_id or str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
        support_level=support_level,
        step_up_at=step_up_at if step_up_at is not None else utcnow(),  # type: ignore[arg-type]
    )


def _client(holder: dict[str, Principal]) -> TestClient:
    app = create_application()

    async def resolve(scope: object) -> Principal:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    app.state.chat.seed_showcase()
    return TestClient(app)


def test_evidence_hold_guest_and_content_gate() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    created = client.post(
        "/api/v1/evidence",
        json={
            "text": "note",
            "mediaType": "text/plain",
            "sourceSystem": "desk",
            "collectionMethod": "api",
        },
        headers={"Idempotency-Key": "http-1"},
    )
    assert created.status_code == 200
    item_id = created.json()["id"]
    assert client.get(f"/api/v1/evidence/{item_id}").status_code == 200
    holder["principal"] = _principal(tenant=uuid.uuid4())
    assert client.get(f"/api/v1/evidence/{item_id}").status_code == 404
    holder["principal"] = _principal(kind="platform_admin", support_level="metadata")
    assert client.get(f"/api/v1/files/{uuid.uuid4()}/content").status_code == 404
    holder["principal"] = _principal(kind="guest", permissions=frozenset())
    forbidden = client.post(
        "/api/v1/conversations",
        json={"agentId": str(demo_id("agent-assistant"))},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "guest_forbidden"
    link = client.post(
        "/api/v1/auth/guest/request-link",
        json={"email": "nobody@example.com", "tenantSlug": "dev"},
    )
    assert link.status_code == 202
    schedules = client.get("/api/v1/retention-schedules")
    holder["principal"] = _principal()
    schedules = client.get("/api/v1/retention-schedules")
    assert schedules.status_code == 200
    low = client.put(
        "/api/v1/retention-schedules/evidence_item",
        json={"retentionDays": 10, "disposition": "delete"},
    )
    assert low.status_code == 422
    assert low.json()["code"] == "retention_below_minimum"
    headers = client.get("/api/v1/evidence").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert "camera=()" in headers["permissions-policy"]


def test_assurance_handlers() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    created = client.post(
        "/api/v1/evidence",
        json={"text": "route", "mediaType": "text/plain", "sourceSystem": "desk"},
        headers={"Idempotency-Key": "routes"},
    )
    assert created.status_code == 200
    item_id = created.json()["id"]
    assert client.get(f"/api/v1/evidence/{item_id}/content").status_code == 200
    assert client.post(f"/api/v1/evidence/{item_id}:verify").status_code == 200
    assert client.get(f"/api/v1/evidence/{item_id}/custody").status_code == 200
    officer = str(demo_id("officer"))
    hold = client.post(
        "/api/v1/legal-holds",
        json={
            "matter": "Route",
            "custodians": [],
            "scopeQuery": {"evidenceIds": [item_id]},
            "approverUserId": officer,
        },
    )
    assert hold.status_code == 200
    hold_id = hold.json()["id"]
    assert client.get("/api/v1/legal-holds").status_code == 200
    assert client.get(f"/api/v1/legal-holds/{hold_id}").status_code == 200
    holder["principal"] = _principal(user_id=officer)
    assert (
        client.post(f"/api/v1/legal-holds/{hold_id}:release", json={"reason": "done"}).status_code
        == 200
    )
    holder["principal"] = _principal()
    assert client.get("/api/v1/disposition-certificates").status_code == 200
    guest = client.post(
        "/api/v1/guests",
        json={"email": "route@example.com", "displayName": "Route"},
    )
    assert guest.status_code == 200
    guest_id = guest.json()["id"]
    assert client.get("/api/v1/guests").status_code == 200
    assert client.get(f"/api/v1/guests/{guest_id}").status_code == 200
    grant = client.post(
        f"/api/v1/guests/{guest_id}/grants",
        json={"portal": "records", "scope": {"evidenceIds": [item_id]}, "watermark": True},
    )
    assert grant.status_code == 200
    assert client.delete(f"/api/v1/guests/{guest_id}/grants/{grant.json()['id']}").status_code in {
        200,
        204,
    }
    assert client.post(f"/api/v1/guests/{guest_id}:revoke").status_code == 200
    session = client.post("/api/v1/auth/guest/session", json={"token": "missing", "totp": ""})
    assert session.status_code >= 400
    assert client.post("/api/v1/auth/guest/totp/enroll").status_code >= 400
    binder = client.post(
        "/api/v1/binders",
        json={"title": "Route", "selection": {"evidenceIds": [item_id]}, "requireReview": False},
    )
    assert binder.status_code == 200
    binder_id = binder.json()["id"]
    assert client.get("/api/v1/binders").status_code == 200
    assert client.get(f"/api/v1/binders/{binder_id}").status_code == 200
    assert client.post(f"/api/v1/binders/{binder_id}:build").status_code == 202
    assert client.get(f"/api/v1/binders/{binder_id}/download").status_code == 200
    cards = client.get("/api/v1/agent-cards")
    assert cards.status_code == 200
    incident = client.post(
        "/api/v1/ai-incidents",
        json={"severity": "low", "summary": "route"},
    )
    assert incident.status_code == 200
    incident_id = incident.json()["id"]
    assert client.get("/api/v1/ai-incidents").status_code == 200
    assert (
        client.patch(f"/api/v1/ai-incidents/{incident_id}", json={"status": "closed"}).status_code
        == 200
    )
    assert client.get("/api/v1/ai-governance/oversight").status_code == 200
    exported_cards = client.post("/api/v1/ai-governance:export", json={"agentIds": []})
    assert exported_cards.status_code == 202
    assert client.get("/api/v1/run-records").status_code == 200
    missing = uuid.uuid4()
    assert client.get(f"/api/v1/run-records/{missing}").status_code == 404
    replay = client.post(f"/api/v1/run-records/{missing}:replay", json={"modelId": ""})
    assert replay.status_code == 404
    assert client.get(f"/api/v1/run-records/{missing}/replays/{missing}").status_code == 404
    assert client.get("/api/v1/tenant/packs").status_code == 200
    assert client.post("/api/v1/tenant/packs/missing:enable").status_code == 404
    assert client.post("/api/v1/tenant/packs/missing:disable").status_code == 404
    assert client.get("/api/v1/me/export").status_code == 200
    assert client.post(f"/api/v1/users/{demo_id('member')}:erase").status_code == 200
    exported = client.post("/api/v1/audit-exports")
    assert exported.status_code == 200
    assert client.get(f"/api/v1/audit-exports/{exported.json()['id']}").status_code == 200
    holder["principal"] = _principal(
        kind="guest",
        user_id=guest_id,
        permissions=frozenset({"evidence:export"}),
    )
    chat = client.app.state.chat
    chat.records["guest_grants"][uuid.uuid4()] = {
        "guest_id": uuid.UUID(guest_id),
        "tenant_id": demo_id("tenant"),
        "scope": {"evidence_ids": [item_id]},
    }
    watermarked = client.get(f"/api/v1/evidence/{item_id}/content")
    assert watermarked.status_code == 415
    assert watermarked.json()["code"] == "watermark_unsupported"
