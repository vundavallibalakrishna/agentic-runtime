"""HTTP surface for tools, connections and the call log."""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


def _client(
    permissions: frozenset[str] | None = None, tenant: uuid.UUID | None = None
) -> TestClient:
    app = demo_application()
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def test_catalogue_register_and_log() -> None:
    client = _client()
    listed = client.get("/api/v1/tool-servers")
    assert listed.status_code == 200
    slugs = {item["slug"] for item in listed.json()["items"]}
    assert "tickets" in slugs
    created = client.post(
        "/api/v1/tool-servers",
        json={
            "slug": "echo",
            "name": "Echo",
            "kind": "remote_mcp",
            "version": {"version": "1.0.0", "endpointUrl": "memory://echo", "authMode": "none"},
        },
    )
    assert created.status_code == 200, created.text
    server_id = created.json()["id"]
    version_id = created.json()["versions"][0]["id"]
    detail = client.get(f"/api/v1/tool-servers/{server_id}/versions/{version_id}")
    tool_version_id = detail.json()["tools"][0]["id"]
    patched = client.patch(
        f"/api/v1/tool-servers/{server_id}/versions/{version_id}/tools/{tool_version_id}",
        json={"riskClass": "R0"},
    )
    assert patched.status_code == 200
    submitted = client.post(f"/api/v1/tool-servers/{server_id}/versions/{version_id}:submit")
    assert submitted.status_code == 200
    approved = client.post(
        f"/api/v1/tool-servers/{server_id}/versions/{version_id}:approve",
        json={"notes": "looks safe"},
    )
    assert approved.status_code == 200
    assert approved.json()["reviewStatus"] == "approved"
    hidden = _client(tenant=uuid.uuid4()).get(f"/api/v1/tool-servers/{server_id}")
    assert hidden.status_code == 404
    reader = _client(permissions=frozenset({"tools:read"}))
    forbidden = reader.post(
        "/api/v1/tool-servers",
        json={
            "slug": "nope",
            "name": "No",
            "version": {"version": "1.0.0", "endpointUrl": "memory://echo"},
        },
    )
    assert forbidden.status_code == 403
    tools = client.get("/api/v1/tools", params={"q": "create_ticket"})
    assert tools.status_code == 200
    # Several servers have a tool of this name. This test means the demo tenant's fixture.
    tool_id = next(
        item["toolId"]
        for item in tools.json()["items"]
        if item["qualifiedName"] == "tickets.create_ticket"
    )
    tested = client.post(
        f"/api/v1/tools/{tool_id}:test", json={"arguments": {"title": "from the console"}}
    )
    assert tested.status_code == 200, tested.text
    assert "TCK-" in str(tested.json().get("resultPreview"))
    console = [
        row
        for row in client.app.state.chat.runs.values()  # type: ignore[attr-defined]
        if row.get("synthetic") is True
    ]
    assert console
    assert console[-1]["trigger"] == "api"
    assert console[-1]["agent_id"]
    log = client.get("/api/v1/tool-calls")
    assert log.status_code == 200
    assert log.json()["items"]
    providers = client.get("/api/v1/credential-providers")
    assert any(item["slug"] == "tickets" for item in providers.json()["items"])
    connections = client.get("/api/v1/connections")
    assert connections.status_code == 200
    assert connections.json()["items"]
    data = client.get("/api/v1/data-connections")
    assert any(item["name"] == "Warehouse" for item in data.json()["items"])


def test_oauth_invalid_grant() -> None:
    client = _client()
    created = client.post(
        "/api/v1/credential-providers",
        json={
            "slug": "local",
            "name": "Local",
            "authorizeUrl": "https://tickets.example/authorize",
            "tokenUrl": "memory://oauth",
        },
    )
    assert created.status_code == 200, created.text
    started = client.post(f"/api/v1/connections/{created.json()['id']}:start")
    assert started.status_code == 200
    bad = client.get(
        "/api/v1/connections/oauth/callback",
        params={"code": "invalid", "state": started.json()["state"]},
    )
    assert bad.status_code == 400
    assert "invalid_grant" in bad.text


def _tool_id(client: TestClient, qualified: str) -> str:
    tools = client.get("/api/v1/tools", params={"limit": 500})
    return next(row["toolId"] for row in tools.json()["items"] if row["qualifiedName"] == qualified)


def test_console_tests_share_a_conversations_folder() -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["id"]
    wrote = client.post(
        f"/api/v1/tools/{_tool_id(client, 'general.write_file')}:test",
        json={
            "arguments": {"path": "notes/kept.txt", "content": "kept"},
            "conversationId": conversation,
        },
    )
    assert wrote.status_code == 200, wrote.text
    read = client.post(
        f"/api/v1/tools/{_tool_id(client, 'general.read_file')}:test",
        json={"arguments": {"path": "notes/kept.txt"}, "conversationId": conversation},
    )
    assert read.status_code == 200, read.text
    assert "kept" in str(read.json().get("resultPreview"))


def test_a_console_test_cannot_use_another_persons_conversation() -> None:
    owner = _client()
    conversation = owner.post("/api/v1/conversations", json={}).json()["id"]
    tool_id = _tool_id(owner, "general.list_files")
    missing = owner.post(
        f"/api/v1/tools/{tool_id}:test",
        json={"arguments": {}, "conversationId": str(uuid.uuid4())},
    )
    assert missing.status_code == 404
    other = Principal(
        kind="user",
        id=str(demo_id("builder")),
        tenant_id=demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="builder@dev.local",
        display_name="Builder",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return other

    owner.app.state.resolve_principal = resolve  # type: ignore[attr-defined]
    refused = owner.post(
        f"/api/v1/tools/{tool_id}:test", json={"arguments": {}, "conversationId": conversation}
    )
    assert refused.status_code == 404
