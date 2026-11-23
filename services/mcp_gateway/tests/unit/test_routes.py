"""Gateway catalogue and execute routes share the tool pipeline."""

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_mcp_gateway.main import create_application
from ar_testing.demo_tenant import seed_demo_tenant
from ar_testing.internal_client import signed_client


def test_internal_routes_reject_a_missing_token() -> None:
    client = TestClient(create_application())
    refused = client.post(
        "/internal/v1/catalog:resolve",
        json={"agentVersionId": "00000000-0000-0000-0000-000000000001", "userId": "u"},
    )
    assert refused.status_code == 401


def test_execute_lists_and_calls_a_seeded_tool() -> None:
    app = create_application()
    client = signed_client(app)
    store = app.state.chat
    # The gateway holds no tenant of its own. This test puts the demo tenant in.
    seed_demo_tenant(store)
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
    missing = signed_client(app, raise_server_exceptions=False).post(
        "/internal/v1/catalog:resolve",
        json={"agentVersionId": str(desk["published_version_id"]), "userId": str(demo_id("admin"))},
    )
    assert missing.status_code == 500


def test_a_console_test_stores_its_run_as_the_conversations_agent() -> None:
    """The gateway stores the run a console test belongs to, with the call, in one place."""
    app = create_application()
    client = signed_client(app)
    store = app.state.chat
    seed_demo_tenant(store)
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    talk = store.create_conversation(demo_id("tenant"), demo_id("admin"), agent_id=desk["id"])
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    tested = client.post(
        "/internal/v1/tool-calls:test",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "conversationId": str(talk["id"]),
            "permissions": ["tools:create"],
            "arguments": {},
            "modelCallId": "test",
        },
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["status"] == "succeeded"
    [run] = [row for row in store.runs.values() if row.get("synthetic") is True]
    assert str(run["conversation_id"]) == str(talk["id"])
    assert run["agent_id"] == desk["id"]
    assert run["trigger"] == "api"
    call = next(row for row in store.tool_calls.values() if row.get("run_id") == run["id"])
    assert call["status"] == "succeeded"
