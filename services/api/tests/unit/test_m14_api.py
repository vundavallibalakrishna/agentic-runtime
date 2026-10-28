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
) -> Principal:
    return Principal(
        kind=kind,  # type: ignore[arg-type]
        id=str(demo_id("admin")),
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
