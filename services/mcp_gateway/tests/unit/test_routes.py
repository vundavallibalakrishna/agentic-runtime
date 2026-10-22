"""Gateway catalogue and execute routes share the tool pipeline."""

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_mcp_gateway.main import create_application


def test_execute_lists_and_calls_a_seeded_tool() -> None:
    app = create_application()
    client = TestClient(app)
    store = app.state.chat
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    catalog = client.post(
        "/internal/v1/catalog:resolve",
        json={"agentVersionId": str(desk["published_version_id"]), "userId": str(demo_id("admin"))},
    )
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["tools"]
    called = client.post(
        "/internal/v1/tool-calls:execute",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "arguments": {},
            "synthetic": True,
            "modelCallId": "list",
        },
    )
    assert called.status_code == 200, called.text
    assert called.json()["status"] == "succeeded"
    tested = client.post(
        "/internal/v1/tool-calls:test",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "arguments": {},
            "dryRun": True,
        },
    )
    assert tested.status_code == 200
    echo = next(row for row in store.tool_servers.values() if row.get("slug") == "files")
    discovered = client.post(
        "/internal/v1/discover",
        json={
            "serverId": str(echo["id"]),
            "versionId": str(echo["current_version_id"]),
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
        },
    )
    assert discovered.status_code in {200, 409, 422}
    app.state.chat = None
    missing = TestClient(app, raise_server_exceptions=False).post(
        "/internal/v1/catalog:resolve",
        json={"agentVersionId": str(desk["published_version_id"]), "userId": str(demo_id("admin"))},
    )
    assert missing.status_code == 500
