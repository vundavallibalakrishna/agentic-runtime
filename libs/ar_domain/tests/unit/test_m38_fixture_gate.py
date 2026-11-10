"""Demo fixtures are seeded only where fake models are allowed. Task: M38-T03."""

from ar_common.settings import EnvName, fake_models_allowed
from ar_domain.agents.logic import assistant_definition
from ar_domain.chat.service import ChatService, demo_id
from ar_testing.demo import demo_store

FIXTURE_SERVERS = {"tickets", "petstore", "warehouse", "web"}
FIXTURE_TOOLS = {"session.checkpoint", "session.propose_change", "web.fetch"}


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


def test_only_dev_and_ci_allow_fakes() -> None:
    assert fake_models_allowed(EnvName.DEV) is True
    assert fake_models_allowed(EnvName.CI) is True
    assert fake_models_allowed(EnvName.STAGING) is False
    assert fake_models_allowed(EnvName.PROD) is False


def test_a_production_store_has_no_fixtures() -> None:
    store = demo_store(fake_models_allowed=False)
    assert _servers(store).isdisjoint(FIXTURE_SERVERS)
    assert _tools(store).isdisjoint(FIXTURE_TOOLS)
    assert "desk" not in _agents(store)
    assert not any(row.get("slug") == "tickets" for row in store.credential_providers.values()), (
        "the demo OAuth provider belongs to the ticket fixture"
    )
    assert demo_id("connection-warehouse") not in store.data_connections


def test_a_production_store_keeps_the_real_tools_and_the_assistant() -> None:
    store = demo_store(fake_models_allowed=False)
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
    assert _control_binding(assistant_definition()) == ["plan_update", "search", "checkpoint"]
