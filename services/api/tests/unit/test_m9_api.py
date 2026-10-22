"""Skills HTTP surface, child runs and cross-tenant 404."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS, SYSTEM_ROLE_PERMISSIONS


def _client(
    *,
    tenant: uuid.UUID | None = None,
    user: str = "admin",
    permissions: frozenset[str] = PERMISSION_KEYS,
) -> TestClient:
    app = create_application()
    principal = Principal(
        kind="user",
        id=str(demo_id(user)),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions,
        team_permissions=frozenset(),
        auth_method="bearer",
        email=f"{user}@dev.local",
        display_name=user,
        roles=frozenset({"tenant_admin"}),
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def test_skills_are_camel_case_and_hidden_across_tenants() -> None:
    admin = _client()
    listed = admin.get("/api/v1/skills")
    assert listed.status_code == 200
    brand = next(row for row in listed.json()["items"] if row["slug"] == "brand-guidelines")
    assert brand["publishedVersion"] == 1
    detail = admin.get(f"/api/v1/skills/{brand['id']}")
    assert detail.status_code == 200
    assert "sentence case" in detail.json()["published"]["instructionsMd"]
    created = admin.post(
        "/api/v1/skills",
        json={
            "slug": "launch-notes",
            "name": "Launch notes",
            "description": "How to write launch notes.",
            "instructionsMd": "Keep the note short.",
        },
    )
    assert created.status_code == 200
    skill_id = created.json()["id"]
    published = admin.post(f"/api/v1/skills/{skill_id}:publish", json={"changeNote": "ready"})
    assert published.status_code == 200
    assert published.json()["publishedVersion"] == 1
    other = _client(tenant=uuid.uuid4())
    hidden = other.get(f"/api/v1/skills/{skill_id}")
    assert hidden.status_code == 404
    member = _client(user="member", permissions=frozenset(SYSTEM_ROLE_PERMISSIONS["member"]))
    blocked = member.post(
        "/api/v1/skills",
        json={
            "slug": "member-skill",
            "name": "Member",
            "description": "No.",
            "instructionsMd": "No.",
        },
    )
    assert blocked.status_code == 403


def test_research_and_writer_runs_are_visible() -> None:
    admin = _client()
    agents = admin.get("/api/v1/agents").json()["items"]
    lead = next(row for row in agents if row["slug"] == "research-lead")
    writer = next(row for row in agents if row["slug"] == "writer")
    research = admin.post("/api/v1/conversations", json={"agentId": lead["id"]})
    posted = admin.post(
        f"/api/v1/conversations/{research.json()['id']}/messages",
        json={"text": "Research the launch notes and the rollout plan"},
    )
    assert posted.status_code == 202
    run_id = posted.json()["run"]["id"]
    run = admin.get(f"/api/v1/runs/{run_id}")
    assert "Merged findings" in run.json()["resultSummary"]
    children = admin.get(f"/api/v1/runs/{run_id}/children")
    assert children.status_code == 200
    assert len(children.json()["items"]) == 2
    assert children.json()["items"][0]["trigger"] == "subagent"
    missing = _client(tenant=uuid.uuid4()).get(f"/api/v1/runs/{run_id}/children")
    assert missing.status_code == 404
    brief = admin.post("/api/v1/conversations", json={"agentId": writer["id"]})
    written = admin.post(
        f"/api/v1/conversations/{brief.json()['id']}/messages",
        json={"text": "Write a one-page brand brief as a docx"},
    )
    body = admin.get(f"/api/v1/runs/{written.json()['run']['id']}").json()
    assert "brand-brief.docx" in body["resultSummary"]
    assert "sentence case" in body["resultSummary"]
