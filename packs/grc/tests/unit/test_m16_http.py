"""GRC HTTP mount: permissions, camelCase and a disabled pack."""

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
        "grc.frameworks:manage",
        "grc.controls:read",
        "grc.controls:manage",
        "grc.evidence:link",
        "evidence:read",
        "evidence:capture",
        "grc.entities:read",
        "grc.entities:manage",
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


def test_catalogue_controls_mappings_evidence_and_entities() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    frameworks = client.get("/api/v1/ext/grc/frameworks").json()["items"]
    skeleton = next(item for item in frameworks if item["licence"] == "skeleton")
    free = next(item for item in frameworks if item["key"] == "nist-csf")
    assert client.get(f"/api/v1/ext/grc/frameworks/{free['id']}").status_code == 200
    exported = client.get(f"/api/v1/ext/grc/frameworks/{free['id']}:export-oscal")
    assert exported.status_code == 200
    assert "prose" in exported.text
    bare = client.get(f"/api/v1/ext/grc/frameworks/{skeleton['id']}:export-oscal")
    assert bare.status_code == 200
    assert "prose" not in bare.text
    requirements = client.get(f"/api/v1/ext/grc/frameworks/{free['id']}/requirements")
    assert requirements.status_code == 200
    if requirements.json()["items"]:
        requirement_id = requirements.json()["items"][0]["id"]
        assert client.get(f"/api/v1/ext/grc/requirements/{requirement_id}").status_code == 200
    owned = client.post(
        "/api/v1/ext/grc/frameworks",
        json={"key": "local-shell", "name": "Local", "version": "1", "licence": "skeleton"},
    )
    assert owned.status_code == 200
    renamed = client.patch(
        f"/api/v1/ext/grc/frameworks/{owned.json()['id']}", json={"name": "Local shell"}
    )
    assert renamed.status_code == 200
    refused = client.patch(f"/api/v1/ext/grc/frameworks/{free['id']}", json={"name": "Nope"})
    assert refused.status_code == 403
    controls = client.get("/api/v1/ext/grc/controls?q=access").json()["items"]
    assert controls
    detail = client.get(f"/api/v1/ext/grc/controls/{controls[0]['id']}")
    assert detail.status_code == 200
    created = client.post(
        "/api/v1/ext/grc/controls",
        json={"key": "local-1", "title": "Local control", "statement": "Do the thing."},
    )
    assert created.status_code == 200
    patched = client.patch(
        f"/api/v1/ext/grc/controls/{created.json()['id']}", json={"title": "Local control updated"}
    )
    assert patched.status_code == 200
    other = client.post(
        "/api/v1/ext/grc/controls",
        json={"key": "local-2", "title": "Second control"},
    ).json()
    mapping = client.post(
        "/api/v1/ext/grc/control-mappings",
        json={
            "fromControlId": created.json()["id"],
            "toControlId": other["id"],
            "confidence": 0.4,
            "rationale": "maybe",
        },
    )
    assert mapping.status_code == 200
    assert mapping.json()["status"] == "suggested"
    listed = client.get("/api/v1/ext/grc/control-mappings?status=suggested")
    assert listed.status_code == 200
    holder["principal"] = Principal(
        kind="user",
        id=str(demo_id("builder")),
        tenant_id=demo_id("tenant"),
        permissions=PERMS,
        auth_method="bearer",
        email="builder@dev.local",
        display_name="Builder",
        roles=frozenset({"builder"}),
    )
    confirmed = client.post(f"/api/v1/ext/grc/control-mappings/{mapping.json()['id']}:confirm")
    assert confirmed.status_code == 200
    rejected_source = client.post(
        "/api/v1/ext/grc/controls",
        json={"key": "local-3", "title": "Third"},
    ).json()
    rejected_target = client.post(
        "/api/v1/ext/grc/controls",
        json={"key": "local-4", "title": "Fourth"},
    ).json()
    pending = client.post(
        "/api/v1/ext/grc/control-mappings",
        json={
            "fromControlId": rejected_source["id"],
            "toControlId": rejected_target["id"],
            "confidence": 0.2,
            "rationale": "weak",
        },
    ).json()
    holder["principal"] = _principal()
    assert (
        client.post(f"/api/v1/ext/grc/control-mappings/{pending['id']}:reject").status_code == 200
    )
    suggested = client.post(
        "/api/v1/ext/grc/control-mappings:suggest",
        json={"fromFrameworkId": free["id"], "toFrameworkId": skeleton["id"]},
    )
    assert suggested.status_code == 202
    evidence = client.post(
        "/api/v1/evidence",
        json={
            "text": "note",
            "mediaType": "text/plain",
            "sourceSystem": "desk",
            "collectionMethod": "api",
        },
        headers={"Idempotency-Key": "grc-evidence"},
    )
    assert evidence.status_code == 200
    linked = client.post(
        "/api/v1/ext/grc/evidence-links",
        json={
            "controlId": created.json()["id"],
            "evidenceItemId": evidence.json()["id"],
            "freshnessDays": 30,
        },
    )
    assert linked.status_code == 200
    assert client.get("/api/v1/ext/grc/evidence-links").status_code == 200
    assert (
        client.delete(f"/api/v1/ext/grc/evidence-links/{linked.json()['id']}").status_code == 204
    )
    parent = client.post(
        "/api/v1/ext/grc/entities", json={"name": "Holdco", "kind": "legal_entity"}
    )
    assert parent.status_code == 200
    child = client.post(
        "/api/v1/ext/grc/entities",
        json={"name": "East", "kind": "division", "parentId": parent.json()["id"]},
    )
    assert child.status_code == 200
    rollup = client.get(f"/api/v1/ext/grc/entities/{parent.json()['id']}/posture")
    assert rollup.status_code == 200
    assert "controlCount" in rollup.json()


def test_frameworks_are_camel_case_and_hidden_when_disabled() -> None:
    holder = {"principal": _principal()}
    client = _client(holder)
    listed = client.get("/api/v1/ext/grc/frameworks")
    assert listed.status_code == 200
    body = listed.json()
    assert body["items"]
    assert "requirementCount" in body["items"][0]
    packs = client.get("/api/v1/tenant/packs")
    assert packs.status_code == 200
    assert any(
        item["packId"] == "grc" and item["enabled"] and item["nav"]
        for item in packs.json()["items"]
    )
    missing = _principal(permissions=frozenset({"grc.frameworks:read"}))
    holder["principal"] = missing
    # same tenant, permission is present; switch tenant instead
    holder["principal"] = _principal(tenant=uuid.uuid4())
    assert client.get("/api/v1/ext/grc/frameworks").status_code == 404
    holder["principal"] = _principal(permissions=frozenset())
    assert client.get("/api/v1/ext/grc/frameworks").status_code == 403
    holder["principal"] = _principal()
    disabled = client.post("/api/v1/tenant/packs/grc:disable")
    assert disabled.status_code == 200
    assert client.get("/api/v1/ext/grc/frameworks").status_code == 404
    assert client.get("/api/v1/ext/grc/controls").status_code == 404
