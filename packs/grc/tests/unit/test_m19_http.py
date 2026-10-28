"""HTTP round trip for the M19 audit routes."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_pack_grc.install import install_for

PERMS = PERMISSION_KEYS | frozenset(
    {
        "grc.audit_portal:manage",
        "grc.campaigns:read",
        "grc.campaigns:manage",
        "grc.reports:export",
        "grc.inspections:manage",
        "grc.privacy:manage",
        "grc.controls:read",
        "grc.controls:manage",
        "grc.risks:manage",
        "grc.risks:read",
    }
)


def _principal(tenant: uuid.UUID | None = None, *, kind: str = "user") -> Principal:
    return Principal(
        kind=kind,  # type: ignore[arg-type]
        id=str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=PERMS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
    )


def test_audit_routes_use_camel_case_and_hide_other_tenants() -> None:
    app = create_application()
    actor = Actor(demo_id("tenant"), demo_id("admin"), PERMS, roles=frozenset({"tenant_admin"}))
    install_for(app.state.chat, actor)
    holder = {"principal": _principal()}

    async def resolve(scope: object) -> Principal:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    client = TestClient(app)
    created = client.post(
        "/api/v1/ext/grc/campaigns",
        json={
            "kind": "access_review",
            "title": "Quarterly access review",
            "audience": {"userIds": [str(actor.user_id)]},
        },
    )
    assert created.status_code == 200
    campaign_id = created.json()["id"]
    started = client.post(f"/api/v1/ext/grc/campaigns/{campaign_id}:start")
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    blocked = client.post(f"/api/v1/ext/grc/campaigns/{campaign_id}:close", json={})
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "open_items"
    items = client.get("/api/v1/ext/grc/campaign-items", params={"campaignId": campaign_id})
    assert items.status_code == 200
    item_id = items.json()["items"][0]["id"]
    decided = client.post(
        f"/api/v1/ext/grc/campaign-items/{item_id}:decide",
        json={"decision": "approve", "statementText": "I reviewed this access."},
    )
    assert decided.status_code == 200
    assert decided.json()["statementHash"]
    rule = client.post(
        "/api/v1/ext/grc/sod-rules",
        json={"name": "Pay and approve", "entitlementA": "pay", "entitlementB": "approve"},
    )
    assert rule.status_code == 200
    rule_id = rule.json()["id"]
    assert client.get("/api/v1/ext/grc/sod-rules").status_code == 200
    renamed = client.patch(f"/api/v1/ext/grc/sod-rules/{rule_id}", json={"name": "Pay"})
    assert renamed.status_code == 200
    assert client.delete(f"/api/v1/ext/grc/sod-rules/{rule_id}").status_code == 204
    pbc = client.post(
        "/api/v1/ext/grc/pbc-requests",
        json={"title": "Population", "ownerUserId": str(actor.user_id)},
    )
    assert pbc.status_code == 200
    assert client.get("/api/v1/ext/grc/pbc-requests").status_code == 200
    absent = client.get(f"/api/v1/ext/grc/pbc-requests/{pbc.json()['id']}/response")
    assert absent.status_code == 404
    imported = client.post("/api/v1/ext/grc/pbc-lists:import", json={"fileId": str(uuid.uuid4())})
    assert imported.status_code == 404
    feed = client.post(
        "/api/v1/ext/grc/entitlements:ingest",
        json={"source": "okta", "connectionId": str(uuid.uuid4())},
    )
    assert feed.status_code == 404
    assert client.get("/api/v1/ext/grc/entitlements").status_code == 200
    missing = client.post(
        "/api/v1/ext/grc/consent-records",
        json={"subjectRef": "ada", "purpose": "mail", "state": "granted"},
    )
    assert missing.status_code == 422
    templates = client.get("/api/v1/ext/grc/report-templates")
    assert templates.status_code == 200
    assert {row["key"] for row in templates.json()["items"]} == {
        "soa",
        "soc2_binder",
        "cscrf",
        "dpdp_breach",
        "board_pack",
    }
    rendered = client.post("/api/v1/ext/grc/reports:render", json={"template": "soa", "params": {}})
    assert rendered.status_code == 202
    assert rendered.json()["binderId"]
    inspection = client.post(
        "/api/v1/ext/grc/inspections",
        json={"regulator": "SEBI", "startedOn": "2026-10-28"},
    )
    assert inspection.status_code == 200
    assert inspection.json()["binderId"]
    dsar = client.post(
        "/api/v1/ext/grc/dsar-requests",
        json={"requestType": "access", "dueAt": "2026-11-28T00:00:00Z"},
    )
    assert dsar.status_code == 200
    fulfilled = client.post(f"/api/v1/ext/grc/dsar-requests/{dsar.json()['id']}:fulfil")
    assert fulfilled.status_code == 200
    assert fulfilled.json()["status"] == "fulfilled"
    assert client.get("/api/v1/ext/grc/dsar-requests").status_code == 200
    assert client.get("/api/v1/ext/grc/consent-records").status_code == 200
    assert client.get("/api/v1/ext/grc/inspections").status_code == 200
    assert client.get("/api/v1/ext/grc/resilience-tests").status_code == 200
    failed = client.post(
        "/api/v1/ext/grc/resilience-tests",
        json={"kind": "bcp", "testedOn": "2026-10-01", "outcome": "fail"},
    )
    assert failed.status_code == 422
    asset = client.post(
        "/api/v1/ext/grc/assets",
        json={
            "name": "Support assistant",
            "kind": "model",
            "ownerUserId": str(actor.user_id),
            "tier": "high",
        },
    )
    assert asset.status_code == 200
    assert asset.json()["kind"] == "model"
    holder["principal"] = _principal(tenant=uuid.uuid4())
    hidden = client.get("/api/v1/ext/grc/pbc-requests")
    assert hidden.status_code == 404
