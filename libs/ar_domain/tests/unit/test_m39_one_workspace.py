"""The sandbox file and command tools are retired and alias to general. Task: M39-T02."""

from __future__ import annotations

import uuid

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.pipeline import ToolPipeline


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def _agent_bound_to(store: object, binding: dict[str, object]) -> uuid.UUID:
    life = AgentLifecycle(store)
    created = life.create(_actor(), slug="worker", name="Worker", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    life.save_draft(_actor(), agent_id, {"instructions": "Work.", "tools": [binding]})
    published = life.publish(_actor(), agent_id, change_note="bound")
    return uuid.UUID(str(published["published_version_id"]))


def _model_names(store: object, version_id: uuid.UUID) -> set[str]:
    catalog = ToolPipeline(store).resolve_catalog(
        agent_version_id=version_id, user_id=demo_id("admin")
    )
    return {str(tool["model_name"]) for tool in catalog["tools"]}


def test_a_whole_sandbox_binding_resolves_to_the_general_computer_tools() -> None:
    from ar_testing.demo import demo_store

    store = demo_store()
    version_id = _agent_bound_to(store, {"server": "sandbox", "include": ["*"]})
    names = _model_names(store, version_id)
    assert names == {
        "general__shell",
        "general__read_file",
        "general__write_file",
        "general__list_files",
    }
    assert not any(name.startswith("sandbox__") for name in names)
    # The network tools of general are not granted by a computer binding.
    assert "general__http" not in names
    assert "general__fetch" not in names


def test_a_specific_sandbox_tool_maps_to_its_general_name() -> None:
    from ar_testing.demo import demo_store

    store = demo_store()
    version_id = _agent_bound_to(store, {"server": "sandbox", "include": ["exec"]})
    assert _model_names(store, version_id) == {"general__shell"}


def test_a_sandbox_binding_entitles_only_the_general_computer_tools() -> None:
    from ar_testing.demo import demo_store

    store = demo_store()
    version_id = _agent_bound_to(store, {"server": "sandbox", "include": ["*"]})
    pipeline = ToolPipeline(store)
    shell = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "general.shell"
    )
    http = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "general.http"
    )
    request = {"agent_version_id": version_id}
    assert pipeline._entitled(request, shell) is True
    assert pipeline._entitled(request, http) is False


def test_the_analyst_is_offered_the_general_computer_not_a_sandbox_tool() -> None:
    from ar_testing.demo import demo_store

    store = demo_store()
    analyst = next(row for row in store.agents.values() if row.get("slug") == "revenue-analyst")
    names = _model_names(store, uuid.UUID(str(analyst["published_version_id"])))
    assert "general__shell" in names
    assert not any(name.startswith("sandbox__") for name in names)
