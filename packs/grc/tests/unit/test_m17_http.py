"""HTTP for control tests, findings and the close guard."""

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
        "grc.frameworks:read",
        "grc.controls:read",
        "grc.controls:manage",
        "grc.evidence:link",
        "grc.tests:read",
        "grc.tests:run",
        "grc.findings:read",
        "grc.findings:manage",
        "evidence:read",
        "evidence:capture",
        "routines:create",
    }
)


def _principal(permissions: frozenset[str] = PERMS, tenant: uuid.UUID | None = None) -> Principal:
    return Principal(
        kind="user",
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
    install_for(
        app.state.chat,
        Actor(demo_id("tenant"), demo_id("admin"), PERMS, roles=frozenset({"tenant_admin"})),
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_run_opens_a_finding_and_close_requires_verified_evidence() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    controls = client.get("/api/v1/ext/grc/controls").json()["items"]
    created = client.post(
        "/api/v1/ext/grc/control-tests",
        json={
            "controlId": controls[0]["id"],
            "key": "aws-http",
            "procedure": "Fail when a rule is not compliant.",
            "schedule": "0 6 * * *",
            "freshnessDays": 30,
        },
    )
    assert created.status_code == 200
    assert "freshnessDays" in created.json()
    run = client.post(f"/api/v1/ext/grc/control-tests/{created.json()['id']}:run")
    assert run.status_code == 202
    body = run.json()
    assert body["outcome"] == "fail"
    assert body["runId"]
    finding_id = body["finding"]["id"]
    refused = client.post(f"/api/v1/ext/grc/findings/{finding_id}:close", json={})
    assert refused.status_code == 409
    assert refused.json()["detail"] == "closure_evidence_required"
    evidence_id = body["evidenceItemIds"][0]
    closed = client.post(
        f"/api/v1/ext/grc/findings/{finding_id}:close",
        json={"evidenceItemId": evidence_id},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    listed = client.get("/api/v1/ext/grc/test-results?outcome=fail")
    assert listed.status_code == 200
    assert listed.json()["items"]
    holder["principal"] = _principal(tenant=uuid.uuid4())
    assert client.get(f"/api/v1/ext/grc/findings/{finding_id}").status_code == 404
    assert (
        client.get(f"/api/v1/ext/grc/control-tests?controlId={created.json()['id']}").status_code
        == 404
    )
    holder["principal"] = _principal(permissions=frozenset())
    assert (
        client.post("/api/v1/ext/grc/findings", json={"title": "x", "severity": "low"}).status_code
        == 403
    )
