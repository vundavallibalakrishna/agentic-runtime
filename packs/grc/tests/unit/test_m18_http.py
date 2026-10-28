"""HTTP round trip for the M18 workflow routes."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_common.errors import ValidationFailedError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_pack_grc.install import install_for
from ar_pack_grc.seed_demo import seed_workflows
from ar_pack_grc.values import as_uuid, choice, scale, string_list, when

PERMS = PERMISSION_KEYS | frozenset(
    {
        "grc.controls:read",
        "grc.controls:manage",
        "grc.questionnaires:read",
        "grc.questionnaires:manage",
        "grc.vendors:read",
        "grc.vendors:manage",
        "grc.policies:read",
        "grc.policies:manage",
        "grc.risks:read",
        "grc.risks:manage",
        "grc.obligations:read",
        "grc.obligations:manage",
        "grc.incidents:read",
        "grc.incidents:manage",
        "grc.exceptions:manage",
        "grc.ethics:manage",
        "grc.campaigns:read",
        "grc.campaigns:manage",
        "evidence:read",
    }
)


def _principal(
    permissions: frozenset[str] = PERMS,
    tenant: uuid.UUID | None = None,
    *,
    kind: str = "user",
) -> Principal:
    return Principal(
        kind=kind,  # type: ignore[arg-type]
        id=str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
    )


def _client(holder: dict[str, Principal]) -> TestClient:
    app = create_application()
    actor = Actor(demo_id("tenant"), demo_id("admin"), PERMS, roles=frozenset({"tenant_admin"}))
    install_for(app.state.chat, actor)
    seed_workflows(app.state.chat, actor)

    async def resolve(scope: object) -> Principal:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_parsers_reject_bad_values() -> None:
    try:
        scale("9")
        raise AssertionError("scale")
    except ValidationFailedError:
        pass
    try:
        choice("nope", frozenset({"a"}), "kind")
        raise AssertionError("choice")
    except ValidationFailedError:
        pass
    try:
        when("not-a-time")
        raise AssertionError("when")
    except ValidationFailedError:
        pass
    assert when(None) is None
    assert as_uuid("", required=False) is None
    assert as_uuid(None, required=False) is None
    try:
        as_uuid("nope")
        raise AssertionError("uuid")
    except ValidationFailedError:
        pass
    try:
        string_list("nope")
        raise AssertionError("list")
    except ValidationFailedError:
        pass


def test_workflow_routes_and_cross_tenant_hide() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    asset = client.post("/api/v1/ext/grc/assets", json={"name": "Vault", "kind": "system"})
    assert asset.status_code == 200, asset.text
    assert client.get("/api/v1/ext/grc/assets").status_code == 200
    risk = client.post(
        "/api/v1/ext/grc/risks",
        json={
            "title": "Flood",
            "statement": "The vault floods.",
            "assetId": asset.json()["id"],
            "likelihood": 2,
            "impact": 2,
        },
    )
    assert risk.status_code == 200, risk.text
    risk_id = risk.json()["id"]
    assert client.get("/api/v1/ext/grc/risks").json()["items"]
    assert client.get(f"/api/v1/ext/grc/risks/{risk_id}").status_code == 200
    patched = client.patch(f"/api/v1/ext/grc/risks/{risk_id}", json={"likelihood": 4, "impact": 4})
    assert patched.json()["assessments"][-1]["score"] == 16
    treatment = client.post(
        f"/api/v1/ext/grc/risks/{risk_id}/treatments",
        json={"kind": "mitigate", "plan": "Raise the floor."},
    )
    assert treatment.status_code == 200, treatment.text
    assert client.get(f"/api/v1/ext/grc/risks/{risk_id}/treatments").json()["items"]
    accepted = client.post(
        f"/api/v1/ext/grc/risks/{risk_id}:accept",
        json={
            "statementText": "Accept the flood risk.",
            "expiresAt": (utcnow() + timedelta(days=10)).isoformat(),
        },
    )
    assert accepted.json()["status"] == "proposed"
    vendor = client.post("/api/v1/ext/grc/vendors", json={"name": "Contoso"})
    assert vendor.status_code == 200, vendor.text
    vendor_id = vendor.json()["id"]
    renamed = client.patch(
        f"/api/v1/ext/grc/vendors/{vendor_id}",
        json={"name": "Contoso Ltd", "tier": "low"},
    )
    assert renamed.json()["tier"] == "low"
    assert client.get(f"/api/v1/ext/grc/vendors/{vendor_id}").status_code == 200
    assert client.get("/api/v1/ext/grc/vendors?q=contoso").json()["items"]
    assessment = client.post(
        f"/api/v1/ext/grc/vendors/{vendor_id}/assessments",
        json={"kind": "questionnaire"},
    )
    assert assessment.status_code == 200
    scored = client.post(
        f"/api/v1/ext/grc/vendor-assessments/{assessment.json()['id']}:score",
        json={"tier": "medium", "rationale": "Questionnaire complete.", "evidenceItemIds": []},
    )
    assert scored.json()["tier"] == "medium"
    assert client.get("/api/v1/ext/grc/campaigns?kind=vendor").json()["items"]
    policy = client.post("/api/v1/ext/grc/policies", json={"key": "backup", "title": "Backup"})
    policy_id = policy.json()["id"]
    version = client.post(
        f"/api/v1/ext/grc/policies/{policy_id}/versions",
        json={"bodyMd": "Backups run nightly. [1]", "changeNote": "draft"},
    )
    assert version.status_code == 200, version.text
    assert client.get(f"/api/v1/ext/grc/policies/{policy_id}").json()["versions"]
    assert client.get("/api/v1/ext/grc/policies").json()["items"]
    review = client.post(f"/api/v1/ext/grc/policies/{policy_id}:submit-review")
    assert review.status_code == 200, review.text
    refused = client.post(f"/api/v1/ext/grc/policy-versions/{version.json()['id']}:publish")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "review_required"
    obligation = client.post(
        "/api/v1/ext/grc/obligations",
        json={"regulator": "TEST", "citation": "s.1", "statement": "Keep a log."},
    )
    assert obligation.status_code == 200, obligation.text
    updated = client.patch(
        f"/api/v1/ext/grc/obligations/{obligation.json()['id']}",
        json={"statement": "Keep a log for 180 days."},
    )
    assert updated.status_code == 200
    assert client.get("/api/v1/ext/grc/obligations?regulator=TEST").json()["items"]
    assert client.get("/api/v1/ext/grc/regulator-feeds").json()["items"]
    assert client.get("/api/v1/ext/grc/regulatory-changes").json()["items"]
    incident = client.post(
        "/api/v1/ext/grc/incidents",
        json={
            "title": "Token leak",
            "detectedAt": utcnow().isoformat(),
            "summary": "A token left chat.",
        },
    )
    incident_id = incident.json()["id"]
    assert client.get("/api/v1/ext/grc/incidents").json()["items"]
    assert client.get(f"/api/v1/ext/grc/incidents/{incident_id}").status_code == 200
    closed = client.patch(f"/api/v1/ext/grc/incidents/{incident_id}", json={"status": "closed"})
    assert closed.json()["status"] == "closed"
    clock = client.post(
        f"/api/v1/ext/grc/incidents/{incident_id}:start-clock",
        json={"regime": "gdpr"},
    )
    assert clock.json()["durationSeconds"] == 72 * 3600
    again = client.post(
        f"/api/v1/ext/grc/incidents/{incident_id}:start-clock",
        json={"regime": "gdpr"},
    )
    assert again.json()["id"] == clock.json()["id"]
    filed = client.post(
        f"/api/v1/ext/grc/incidents/{incident_id}:file-notification",
        json={"regime": "gdpr", "bodyMd": "We will notify."},
    )
    assert filed.status_code == 200
    assert filed.json()["status"] == "proposed"
    library = client.get("/api/v1/ext/grc/answer-library")
    assert library.status_code == 200
    answer = client.post(
        "/api/v1/ext/grc/answer-library",
        json={
            "question": "Who owns backups?",
            "answerMd": "The platform team.",
            "citations": ["owner"],
        },
    )
    approved = client.patch(
        f"/api/v1/ext/grc/answer-library/{answer.json()['id']}",
        json={"status": "approved"},
    )
    assert approved.json()["status"] == "approved"
    job_id = library.json()["jobs"][0]["id"]
    exported = client.post(f"/api/v1/ext/grc/questionnaires/{job_id}:export")
    assert exported.status_code == 409
    assert exported.json()["detail"] == "review_required"
    controls = client.get("/api/v1/ext/grc/controls").json()["items"]
    waiver = client.post(
        "/api/v1/ext/grc/exceptions",
        json={
            "controlId": controls[0]["id"],
            "kind": "waiver",
            "rationale": "Missing the compensating control.",
            "expiresAt": (utcnow() + timedelta(days=3)).isoformat(),
        },
    )
    assert waiver.status_code == 422
    created = client.post(
        "/api/v1/ext/grc/exceptions",
        json={
            "controlId": controls[0]["id"],
            "kind": "exception",
            "rationale": "A short exception.",
            "expiresAt": (utcnow() + timedelta(days=3)).isoformat(),
        },
    )
    assert created.status_code == 200, created.text
    assert client.get("/api/v1/ext/grc/exceptions").json()["items"]
    ethics = client.post("/api/v1/ext/grc/ethics-cases", json={"title": "Concern"})
    assert ethics.status_code == 200, ethics.text
    case_id = ethics.json()["id"]
    assert client.get("/api/v1/ext/grc/ethics-cases").json()["items"]
    holder["principal"] = _principal(frozenset({"audit:read"}))
    hidden = client.get(f"/api/v1/ext/grc/ethics-cases/{case_id}")
    assert hidden.status_code == 404
    assert client.get("/api/v1/ext/grc/vendors").status_code == 403
    holder["principal"] = _principal(tenant=uuid.uuid4())
    assert client.get(f"/api/v1/ext/grc/risks/{risk_id}").status_code == 404
    assert client.get(f"/api/v1/ext/grc/vendors/{vendor_id}").status_code == 404
    assert client.get(f"/api/v1/ext/grc/policies/{policy_id}").status_code == 404
    assert client.get(f"/api/v1/ext/grc/incidents/{incident_id}").status_code == 404
