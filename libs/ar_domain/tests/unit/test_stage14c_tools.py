"""The default assistant can chart a table, and a written file gets its real type. Proof: unit."""

import copy

from ar_domain.agents.logic import assistant_definition, definition_hash
from ar_domain.files.logic import mime_of_name
from ar_domain.tools.general import _mime
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


def _migration() -> object:
    import importlib

    return importlib.import_module(
        "ar_domain.migrations.versions.20261111_0044_assistant_table_tools"
    )


def test_the_migration_adds_the_grants_a_seeded_assistant_lacks() -> None:
    migration = _migration()
    old = assistant_definition()
    for grant in old["tools"]:  # type: ignore[union-attr]
        if grant.get("server") == "general":
            grant["include"] = ["code", "shell"]
    old["tools"] = [g for g in old["tools"] if g.get("server") != "image"]  # type: ignore[union-attr]
    before = copy.deepcopy(old)
    fresh = migration.with_grants(old)  # type: ignore[attr-defined]
    assert old == before
    assert fresh is not None
    assert _TABLE_TOOLS <= set(_general(fresh))
    assert any(g.get("server") == "image" for g in fresh["tools"])
    assert migration._hash(fresh) == definition_hash(fresh)  # type: ignore[attr-defined]


def test_the_migration_leaves_a_complete_or_wildcard_grant_alone() -> None:
    migration = _migration()
    assert migration.with_grants(assistant_definition()) is None  # type: ignore[attr-defined]
    wide = {
        "tools": [
            {"server": "general", "version": "*", "include": ["*"]},
            {"server": "image", "version": "*", "include": ["*"]},
        ]
    }
    assert migration.with_grants(wide) is None  # type: ignore[attr-defined]


def test_a_written_file_is_typed_by_its_name() -> None:
    assert _mime("report.html") == "text/html"
    assert _mime("notes.txt") == "text/plain"
    assert _mime("notes.md") == "text/markdown"
    assert _mime("rows.tsv") == "text/csv"
    assert _mime("chart.PNG") == "image/png"
    assert _mime("unknown") == "text/plain"
    assert mime_of_name("blob.bin", "application/octet-stream") == "application/octet-stream"


def test_an_assistant_asked_for_a_chart_is_offered_the_chart_tool() -> None:
    import asyncio
    import uuid

    from ar_domain.chat.service import demo_id

    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)

    class _Search:
        def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
            del query, limit
            return []

    # A tenant with web search and a vision model, so the assistant has its whole
    # catalogue and is over the threshold. A tool the tenant has not set up is not offered.
    store.search_provider = _Search()
    store._alias_target = lambda _t, _alias: ({}, {"capabilities": ["chat", "vision"]})
    captured: list[list[str]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tenant_id, model_alias
        captured.append([str(tool["function"]["name"]) for tool in tools])  # type: ignore[index]
        return {
            "text": "Done.",
            "tool_calls": [],
            "usage": {"tokens_in": 2, "tokens_out": 2},
            "real": True,
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    request = "Draw a bar chart with North 2 and South 5."
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), request, schedule=False
    )
    asyncio.run(store.generate(uuid.UUID(str(posted["run"]["id"])), request, []))
    # The assistant has more tools than the threshold, so the model is not sent them all.
    assert "session__search" in captured[0]
    assert "general__chart" in captured[0]
    assert len(captured[0]) < 20


def test_the_chart_tool_plots_a_table_file_in_the_working_folder() -> None:
    import uuid

    from ar_domain.chat.service import demo_id
    from ar_domain.tools.charts import dispatch_chart
    from ar_domain.tools.general import _prepare

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "chart it", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    arguments: dict[str, object] = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_run_id": run["id"],
        "_conversation_id": run["conversation_id"],
        "kind": "bar",
        "path": "inputs/regions.csv",
        "xKey": "region",
        "yKey": "count",
    }
    root = _prepare(store, arguments)
    target = root / "workspace" / "inputs" / "regions.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("region,count\nNorth,12\nSouth,19\n", encoding="utf-8")
    drawn = dispatch_chart(store, "chart", arguments)
    assert drawn is not None and drawn["is_error"] is False
    shown = drawn["structured"]["presentation"]  # type: ignore[index]
    assert shown["rows"] == [{"label": "North", "value": 12.0}, {"label": "South", "value": 19.0}]
    missing = dispatch_chart(store, "chart", {**arguments, "path": "inputs/none.csv"})
    assert missing is not None and missing["is_error"] is True


def test_the_code_tool_points_at_the_chart_tool() -> None:
    store = demo_store()
    code = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "general.code"
    )
    chart = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "general.chart"
    )
    assert "general.chart" in str(code["description"])
    assert "path" in chart["input_schema"]["properties"]
    assert "required" not in chart["input_schema"]


def test_a_script_missing_a_package_is_told_to_use_the_chart_tool() -> None:
    from types import SimpleNamespace

    from ar_domain.tools import general

    failed = SimpleNamespace(exit_code=1, stderr="ModuleNotFoundError: No module named 'x'")
    kept = SimpleNamespace(exit_code=1, stderr="ValueError: bad")
    general.replace = lambda result, **changes: SimpleNamespace(**{**vars(result), **changes})  # type: ignore[attr-defined]
    try:
        assert "general.chart" in general._missing_package(failed).stderr  # type: ignore[arg-type]
        assert general._missing_package(kept) is kept  # type: ignore[arg-type]
    finally:
        from dataclasses import replace

        general.replace = replace  # type: ignore[attr-defined]


def _run_arguments(store: object) -> dict[str, object]:
    import uuid

    from ar_domain.chat.service import demo_id

    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)  # type: ignore[attr-defined]
    posted = store.post_message(  # type: ignore[attr-defined]
        tenant, user, uuid.UUID(str(conversation["id"])), "write", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]  # type: ignore[attr-defined]
    return {
        "_tenant_id": tenant,
        "_user_id": user,
        "_run_id": run["id"],
        "_conversation_id": run["conversation_id"],
    }


def test_writing_bytes_that_are_already_stored_still_saves_the_folder() -> None:
    from ar_domain.tools.general import _prepare, _store_file

    store = demo_store()
    first = _run_arguments(store)
    root = _prepare(store, first)
    (root / "workspace" / "data").mkdir(parents=True, exist_ok=True)
    (root / "workspace" / "data" / "same.csv").write_text("a,b\\n1,2\\n", encoding="utf-8")
    _store_file(store, first, name="same.csv", data=b"a,b\\n1,2\\n")
    # A second run in the same conversation writes the same bytes under the same name.
    second = {**first, "_run_id": _run_arguments(store)["_run_id"]}
    root = _prepare(store, second)
    (root / "workspace" / "again").mkdir(parents=True, exist_ok=True)
    (root / "workspace" / "again" / "same.csv").write_text("a,b\\n1,2\\n", encoding="utf-8")
    _store_file(store, second, name="same.csv", data=b"a,b\\n1,2\\n")
    saved = {
        str(row.get("path"))
        for row in store.workspace_files.values()
        if row.get("run_id") == second["_run_id"]
    }
    assert "again/same.csv" in saved


def test_another_persons_detached_file_is_not_this_runs_artifact() -> None:
    import hashlib

    from ar_domain.chat.service import demo_id
    from ar_domain.tools.general import _same_artifact

    store = demo_store()
    arguments = _run_arguments(store)
    digest = hashlib.sha256(b"shared bytes").hexdigest()
    other = store.upload(  # type: ignore[attr-defined]
        demo_id("tenant"), demo_id("builder"), "same.txt", "text/plain", b"shared bytes"
    )
    assert other["id"]
    assert _same_artifact(store, arguments, "same.txt", digest) is None


def test_markdown_text_added_to_knowledge_keeps_its_sections() -> None:
    from ar_domain.knowledge.members import _plain

    text = (
        "# Policy\n\n## Access\n\nApproved by the duty manager.\n\n## Retention\n\nKept 7 years.\n"
    )
    passages = _plain(text, "Policy")
    assert [row["heading"] for row in passages] == ["Policy / Access", "Policy / Retention"]
    assert "duty manager" in passages[0]["text"]
    assert _plain("<p>Hello   <b>world</b></p>", "Note")[0]["text"] == "Hello world"


def test_a_query_that_names_the_path_is_told_the_table_names() -> None:
    from ar_domain.tools.analysis import dispatch_analysis
    from ar_domain.tools.general import _prepare

    store = demo_store()
    arguments = _run_arguments(store)
    root = _prepare(store, arguments)
    target = root / "workspace" / "data" / "regions.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("region,count\nNorth,12\nSouth,19\n", encoding="utf-8")
    wrong = dispatch_analysis(
        store,
        "query_table",
        {**arguments, "path": "data/regions.csv", "sql": "SELECT SUM(count) FROM data/regions.csv"},
    )
    assert wrong is not None and wrong["is_error"] is True
    assert "The tables are: regions" in str(wrong["text"])
    # A quoted path parses, and the engine then refuses to open the file. Same answer.
    quoted = dispatch_analysis(
        store,
        "query_table",
        {**arguments, "path": "data/regions.csv", "sql": "SELECT SUM(count) FROM 'regions.csv'"},
    )
    assert quoted is not None and quoted["code"] == "sql_rejected"
    assert "The tables are: regions" in str(quoted["text"])
    right = dispatch_analysis(
        store,
        "query_table",
        {**arguments, "path": "data/regions.csv", "sql": "SELECT SUM(count) AS total FROM regions"},
    )
    assert right is not None and right["is_error"] is False
    assert "31" in str(right["text"])
