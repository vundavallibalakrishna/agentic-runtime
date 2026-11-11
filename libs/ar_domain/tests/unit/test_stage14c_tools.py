"""The default assistant can chart a table, and a written file gets its real type. Proof: unit."""

import copy

from ar_domain.agents.logic import assistant_definition, definition_hash
from ar_domain.files.logic import mime_of_name
from ar_domain.tools.general import _mime
from ar_domain.tools.seed_tools import _add_grants, _grant_template
from ar_testing.demo import demo_store

_TABLE_TOOLS = {"inspect_table", "query_table", "pivot_table", "export_table", "chart"}


def _general(definition: dict[str, object]) -> list[str]:
    tools = definition["tools"]
    assert isinstance(tools, list)
    for grant in tools:
        if isinstance(grant, dict) and grant.get("server") == "general":
            include = grant["include"]
            assert isinstance(include, list)
            return [str(name) for name in include]
    return []


def test_the_template_grants_the_chart_and_table_tools() -> None:
    definition = assistant_definition()
    assert _TABLE_TOOLS <= set(_general(definition))
    assert "general.chart" in str(definition["instructions"])


def test_every_granted_general_tool_is_in_the_catalogue() -> None:
    store = demo_store()
    known = {
        str(row.get("qualified_name"))
        for row in store.tool_versions.values()
        if isinstance(row, dict)
    }
    for name in _general(assistant_definition()):
        assert f"general.{name}" in known


def _seeded(store: object) -> tuple[dict[str, object], dict[str, object]]:
    for agent in store.agents.values():  # type: ignore[attr-defined]
        if agent.get("slug") == "assistant":
            return agent, store.versions[agent["published_version_id"]]  # type: ignore[attr-defined]
    raise AssertionError("no assistant")


def test_a_seeded_assistant_gains_the_template_grants() -> None:
    store = demo_store()
    _agent, version = _seeded(store)
    definition = version["definition"]
    assert isinstance(definition, dict)
    for grant in definition["tools"]:
        if grant.get("server") == "general":
            grant["include"] = ["code", "shell"]
    version["change_note"] = "seed"
    _grant_template(store)
    assert _TABLE_TOOLS <= set(_general(definition))
    assert version["definition_hash"] == definition_hash(copy.deepcopy(dict(definition)))


def test_a_version_an_administrator_published_is_left_alone() -> None:
    store = demo_store()
    _agent, version = _seeded(store)
    definition = version["definition"]
    assert isinstance(definition, dict)
    for grant in definition["tools"]:
        if grant.get("server") == "general":
            grant["include"] = ["code"]
    version["change_note"] = "tightened by the administrator"
    _grant_template(store)
    assert _general(definition) == ["code"]


def test_grants_are_added_once_and_a_wildcard_is_kept() -> None:
    tools: list[object] = [{"server": "documents", "version": "*", "include": ["*"]}]
    wanted = [
        {"server": "documents", "version": "*", "include": ["read"]},
        {"server": "image", "version": "*", "include": ["ask"]},
    ]
    assert _add_grants(tools, wanted) is True
    assert tools[0] == {"server": "documents", "version": "*", "include": ["*"]}
    assert tools[1] == {"server": "image", "version": "*", "include": ["ask"]}
    assert _add_grants(tools, wanted) is False


def test_a_written_file_is_typed_by_its_name() -> None:
    assert _mime("report.html") == "text/html"
    assert _mime("notes.txt") == "text/plain"
    assert _mime("notes.md") == "text/markdown"
    assert _mime("rows.tsv") == "text/csv"
    assert _mime("chart.PNG") == "image/png"
    assert _mime("unknown") == "text/plain"
    assert mime_of_name("blob.bin", "application/octet-stream") == "application/octet-stream"
