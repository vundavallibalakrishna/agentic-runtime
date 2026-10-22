"""Memory HTTP surface, scope visibility and audit."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client(
    *,
    tenant: uuid.UUID | None = None,
    user: str = "admin",
    permissions: frozenset[str] = PERMISSION_KEYS,
    roles: frozenset[str] = frozenset({"tenant_admin"}),
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
        roles=roles,
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def _shared() -> tuple[TestClient, object]:
    """One process store so the member sees the same assistant the admin listed."""
    app = create_application()
    holder = {
        "user": "admin",
        "permissions": PERMISSION_KEYS,
        "roles": frozenset({"tenant_admin"}),
    }

    async def resolve(scope: object) -> Principal:
        del scope
        return Principal(
            kind="user",
            id=str(demo_id(str(holder["user"]))),
            tenant_id=demo_id("tenant"),
            permissions=holder["permissions"],  # type: ignore[arg-type]
            team_permissions=frozenset(),
            auth_method="bearer",
            email=f"{holder['user']}@dev.local",
            display_name=str(holder["user"]),
            roles=holder["roles"],  # type: ignore[arg-type]
        )

    def become(user: str, permissions: frozenset[str], roles: frozenset[str]) -> None:
        holder["user"] = user
        holder["permissions"] = permissions
        holder["roles"] = roles

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app), become


def test_memory_crud_is_scoped_audited_and_camel_case() -> None:
    admin, become = _shared()
    listed = admin.get("/api/v1/memory")
    assert listed.status_code == 200
    body = listed.json()
    assert body["memoryEnabled"] is True
    assert any("one page" in item["content"] for item in body["items"])
    assert "sourceKind" in body["items"][0]
    assert "source_kind" not in body["items"][0]
    platform = next(team for team in body["teams"] if team["name"] == "Platform")
    assert any("date first" in item["content"] for item in platform["items"])
    created = admin.post(
        "/api/v1/memory",
        json={"content": "Prefers the date written as day month year.", "category": "preference"},
    )
    assert created.status_code == 200
    fact_id = created.json()["id"]
    patched = admin.patch(f"/api/v1/memory/{fact_id}", json={"content": "Prefers ISO dates."})
    assert patched.status_code == 200
    assert patched.json()["content"] == "Prefers ISO dates."
    secret = admin.post("/api/v1/memory", json={"content": "password: hunter2"})
    assert secret.status_code == 422
    missing = admin.delete("/api/v1/memory")
    assert missing.status_code == 422
    removed = admin.delete(f"/api/v1/memory/{fact_id}")
    assert removed.status_code == 200
    audit = admin.get("/api/v1/audit-events")
    assert audit.status_code == 200
    actions = {row["action"] for row in audit.json()["items"]}
    assert {"memory.created", "memory.updated", "memory.deleted"} <= actions
    outsider = _client(tenant=uuid.uuid4())
    hidden = outsider.patch(f"/api/v1/memory/{fact_id}", json={"content": "stolen"})
    assert hidden.status_code == 404
    agents = admin.get("/api/v1/agents").json()["items"]
    assistant = next(agent for agent in agents if agent["slug"] == "assistant")
    become("member", frozenset({"chat:use"}), frozenset({"member"}))
    member = admin
    own = member.get("/api/v1/memory")
    assert own.status_code == 200
    assert all("one page" not in item["content"] for item in own.json()["items"])
    assert any(
        "date first" in item["content"] for team in own.json()["teams"] for item in team["items"]
    )
    proposed = member.post(
        f"/api/v1/agents/{assistant['id']}/memory",
        json={"content": "Mention the side door.", "category": "lesson"},
    )
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "pending_review"
    become("admin", PERMISSION_KEYS, frozenset({"tenant_admin"}))
    queue = admin.get(f"/api/v1/agents/{assistant['id']}/memory?status=pending_review")
    assert queue.status_code == 200
    assert any(item["content"] == "Mention the side door." for item in queue.json()["items"])
    become("member", frozenset({"chat:use"}), frozenset({"member"}))
    denied = member.get(f"/api/v1/agents/{assistant['id']}/memory")
    assert denied.status_code == 403
    become("admin", PERMISSION_KEYS, frozenset({"tenant_admin"}))
    approved = admin.post(
        f"/api/v1/agents/{assistant['id']}/memory/{proposed.json()['id']}:approve"
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "active"
    conversation = admin.post("/api/v1/conversations", json={"agentId": assistant["id"]})
    conversation_id = conversation.json()["id"]
    sent = admin.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "Remember that I prefer answers in bullet points."},
    )
    assert sent.status_code == 202
    again = admin.get("/api/v1/memory")
    assert any("bullet points" in item["content"] for item in again.json()["items"])
    toggled = admin.patch("/api/v1/memory/settings", json={"enabled": False})
    assert toggled.status_code == 200
    assert toggled.json()["memoryEnabled"] is False
