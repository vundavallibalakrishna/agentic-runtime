"""Demo fixtures are seeded only where fake models are allowed. Task: M38-T03."""

from ar_domain.agents.logic import assistant_definition
from ar_domain.chat.service import ChatService, demo_id
from ar_testing.demo import demo_store

FIXTURE_SERVERS = {"tickets", "petstore", "warehouse", "proposals"}
FIXTURE_TOOLS = {"proposals.propose_change"}


def _servers(store: ChatService) -> set[str]:
    return {str(row["slug"]) for row in store.tool_servers.values()}


def _tools(store: ChatService) -> set[str]:
    return {str(row["qualified_name"]) for row in store.tool_versions.values()}


def _agents(store: ChatService) -> set[str]:
    return {str(row["slug"]) for row in store.agents.values()}


def _control_binding(definition: dict[str, object]) -> list[str]:
    tools = definition["tools"]
    assert isinstance(tools, list)
    binding = next(row for row in tools if row["server"] == "session")
    return list(binding["include"])


def test_a_production_store_has_no_fixtures() -> None:
    store = demo_store(stand_in_tools=False)
    assert _servers(store).isdisjoint(FIXTURE_SERVERS)
    assert _tools(store).isdisjoint(FIXTURE_TOOLS)
    assert "desk" not in _agents(store)
    assert not any(row.get("slug") == "tickets" for row in store.credential_providers.values()), (
        "the demo OAuth provider belongs to the ticket fixture"
    )
    assert demo_id("connection-warehouse") not in store.data_connections


def test_a_production_store_keeps_the_real_tools_and_the_assistant() -> None:
    store = demo_store(stand_in_tools=False)
    tools = _tools(store)
    for name in (
        "files.read",
        "session.plan_update",
        "session.search",
        "session.a2a_call",
        "general.fetch",
        "general.code",
        "documents.read",
    ):
        assert name in tools
    assert "assistant" in _agents(store)
    assistant = next(row for row in store.agents.values() if row["slug"] == "assistant")
    definition = store.versions[assistant["published_version_id"]]["definition"]
    assert _control_binding(definition) == ["plan_update", "search"]


def test_a_dev_store_keeps_the_fixtures() -> None:
    store = demo_store()
    assert FIXTURE_SERVERS <= _servers(store)
    assert FIXTURE_TOOLS <= _tools(store)
    assert "desk" in _agents(store)
    assert _control_binding(assistant_definition()) == ["plan_update", "search"]


def _stale_session_tool(store: ChatService, name: str) -> dict[str, object]:
    """Add a session tool the way a release that still shipped it would have seeded it."""
    from ar_domain.tools.seed_tools import _add_tool, _platform_server

    server = _platform_server(store, "session")
    assert server is not None
    item = {
        "name": name,
        "title": "Gone",
        "description": "A tool an earlier release shipped.",
        "input_schema": {"type": "object", "properties": {}},
        "risk_class": "R0",
    }
    _add_tool(store, server, server["current_version_id"], "session", item)
    return next(
        row for row in store.tool_defs.values() if row["qualified_name"] == f"session.{name}"
    )


def test_a_built_in_tool_this_release_no_longer_ships_is_retired() -> None:
    """An install seeded earlier stops offering a tool the product has removed. OQ-148."""
    from ar_domain.tools.pipeline import ToolPipeline
    from ar_domain.tools.seed_tools import refresh_builtins
    from ar_testing.retry_tool import QUALIFIED_NAME, offer_retry_tool

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    offer_retry_tool(store, tenant)
    stale = _stale_session_tool(store, "checkpoint")
    assert stale["disabled_at"] is None
    refresh_builtins(store)
    assert stale["disabled_at"] is not None
    assert stale["disabled_reason"]
    offered = ToolPipeline(store)._bound("session", ["*"], user, tenant)
    names = {str(row["qualified_name"]) for row in offered}
    assert "session.checkpoint" not in names
    assert {"session.plan_update", "session.search"} <= names
    version = next(
        row for row in store.tool_versions.values() if row["qualified_name"] == "session.checkpoint"
    )
    refused = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": user,
            "tool_version_id": version["id"],
            "arguments": {"note": "x"},
        }
    )
    assert refused["error"]["code"] == "tool_disabled"  # type: ignore[index]
    # Nothing else is touched: shipped tools, the demo servers and a
    # server registered from outside the product stay as they were.
    disabled = {
        str(row["qualified_name"])
        for row in store.tool_defs.values()
        if row.get("disabled_at") is not None
    }
    assert disabled == {"session.checkpoint"}
    assert QUALIFIED_NAME in _tools(store)


def test_an_install_seeded_earlier_retires_the_approval_test_tool() -> None:
    """``session.propose_change`` was in the catalogue of a dev or CI install. OQ-196."""
    from ar_domain.tools.seed_tools import refresh_builtins

    store = demo_store()
    stale = _stale_session_tool(store, "propose_change")
    refresh_builtins(store)
    assert stale["disabled_at"] is not None


def _migration() -> object:
    import importlib

    return importlib.import_module(
        "ar_domain.migrations.versions.20261119_0053_assistant_without_checkpoint"
    )


def test_the_migration_takes_the_checkpoint_grant_from_a_seeded_assistant() -> None:
    from ar_domain.agents.logic import definition_hash

    migration = _migration()
    old = assistant_definition()
    granted = old["tools"]
    assert isinstance(granted, list)
    old["tools"] = [
        {**grant, "include": ["plan_update", "search", "checkpoint"]}
        if grant.get("server") == "session"
        else grant
        for grant in granted
    ]
    fresh = migration.without_grant(old)  # type: ignore[attr-defined]
    assert fresh is not None
    assert fresh == assistant_definition()
    assert _control_binding(old) == ["plan_update", "search", "checkpoint"]
    assert migration._hash(fresh) == definition_hash(fresh)  # type: ignore[attr-defined]
    back = migration.with_grant(fresh)  # type: ignore[attr-defined]
    assert back == old
    assert _control_binding(fresh) == ["plan_update", "search"]


def test_the_migration_leaves_other_grants_alone() -> None:
    migration = _migration()
    assert migration.without_grant(assistant_definition()) is None  # type: ignore[attr-defined]
    wide = {"tools": [{"server": "session", "version": "*", "include": ["*"]}]}
    assert migration.without_grant(wide) is None  # type: ignore[attr-defined]
    assert migration.with_grant(wide) == wide  # type: ignore[attr-defined]
    elsewhere = {"tools": [{"server": "notes", "version": "*", "include": ["checkpoint"]}]}
    assert migration.without_grant(elsewhere) is None  # type: ignore[attr-defined]
    only = {"tools": [{"server": "session", "version": "*", "include": ["checkpoint"]}]}
    assert migration.without_grant(only) == {"tools": []}  # type: ignore[attr-defined]
    assert migration.with_grant({"tools": []}) == only  # type: ignore[attr-defined]
    assert migration.without_grant({}) is None  # type: ignore[attr-defined]
    assert migration._OURS == (  # type: ignore[attr-defined]
        "seed",
        "offline-default",
        "sample-and-saved-queries",
    )
