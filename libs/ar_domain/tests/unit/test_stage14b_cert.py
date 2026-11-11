"""Stage 14b: tool-call identity, structured output, artifacts and attachments."""

from __future__ import annotations

import asyncio
import uuid

from ar_domain.chat.service import demo_id
from ar_domain.documents.library import DocumentLibrary
from ar_domain.models.request import chat_completion_body, redact_provider_error
from ar_domain.tools.identity import tool_call_idempotency_key
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.structured import accept_output
from ar_testing.demo import demo_store

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def test_idempotency_key_changes_with_the_query_and_matches_a_retry() -> None:
    first = tool_call_idempotency_key(
        run_id="run",
        model_call_id="research:q1:0:search",
        step="research",
        query_id="q1",
        call_index=0,
        qualified_name="research.search",
    )
    second = tool_call_idempotency_key(
        run_id="run",
        model_call_id="research:q2:0:search",
        step="research",
        query_id="q2",
        call_index=0,
        qualified_name="research.search",
    )
    again = tool_call_idempotency_key(
        run_id="run",
        model_call_id="research:q1:0:search",
        step="research",
        query_id="q1",
        call_index=0,
        qualified_name="research.search",
    )
    assert first != second
    assert first == again


def test_a_retried_chart_call_keeps_one_file() -> None:
    store = demo_store()
    version = _version(store, "general.chart")
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Draw the chart", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    request = {
        "tenant_id": tenant,
        "user_id": user,
        "run_id": run_id,
        "agent_id": store.runs[run_id]["agent_id"],
        "agent_version_id": store.runs[run_id].get("agent_version_id"),
        "tool_version_id": version["id"],
        "arguments": {
            "kind": "bar",
            "title": "Regions",
            "xKey": "region",
            "yKey": "count",
            "rows": [{"region": "North", "count": 2}, {"region": "South", "count": 5}],
        },
        "model_call_id": "call_chart",
        "step": 1,
        "call_index": 1,
    }
    pipeline = ToolPipeline(store)
    first = pipeline.execute(request)
    assert first["status"] == "succeeded"
    second = pipeline.execute(dict(request))
    assert second.get("replayed") is True
    assert second["tool_call_id"] == first["tool_call_id"]
    charts = [
        row
        for row in store.files.values()
        if str(row.get("name") or "").endswith(".png") and row.get("run_id") == run_id
    ]
    assert len(charts) == 1


def test_two_research_queries_and_a_retry_keep_their_sources() -> None:
    from ar_runtime.activities.expire_approval import bind_store
    from ar_runtime.activities.research_step import research_step, research_subtask

    store = demo_store()
    bind_store(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    question = "What do the stored notes say about a kite. What do they say about the string."
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        question,
        research=True,
        schedule=False,
    )
    run_id = str(posted["run"]["id"])
    step = asyncio.run(research_step({"run_id": run_id, "text": question}))
    assert step["kind"] == "fanout"
    subtasks = step["subtasks"]
    assert len(subtasks) >= 2
    done = [asyncio.run(research_subtask({"run_id": run_id, **item})) for item in subtasks[:2]]
    assert all(item.get("status") == "done" and item.get("sources") for item in done)
    before = len(store.tool_calls)
    again = asyncio.run(research_subtask({"run_id": run_id, **subtasks[0]}))
    assert again.get("status") == "done"
    assert again.get("sources")
    assert len(store.tool_calls) == before
    keys = {str(row.get("idempotency_key")) for row in store.tool_calls.values()}
    assert len(keys) == before


def test_writer_adopts_a_duplicate_idempotency_key() -> None:
    from ar_domain.durable.m28 import save_tool_calls

    tenant = uuid.uuid4()
    run_id = uuid.uuid4()
    stored = uuid.uuid4()
    fresh = uuid.uuid4()

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def first(self) -> dict[str, object] | None:
            return self._rows[0] if self._rows else None

        def mappings(self) -> list[dict[str, object]]:
            return self._rows

    class Session:
        def __init__(self) -> None:
            self.sql: list[str] = []

        async def execute(self, statement: object, params: object = None) -> Result:
            del params
            sql = str(statement)
            self.sql.append(sql)
            if "FROM runs" in sql:
                return Result([{"id": run_id}])
            if "FROM tool_calls" in sql:
                return Result([{"id": stored, "status": "succeeded"}])
            return Result([])

    session = Session()
    adopted = asyncio.run(
        save_tool_calls(
            session,  # type: ignore[arg-type]
            [
                {
                    "id": fresh,
                    "tenant_id": tenant,
                    "run_id": run_id,
                    "qualified_name": "general.chart",
                    "idempotency_key": f"{run_id}:call_chart",
                    "status": "succeeded",
                    "result_preview": "again",
                }
            ],
        )
    )
    assert adopted[fresh] == stored
    assert not any(sql.strip().startswith("INSERT") for sql in session.sql)


def test_structured_output_strips_a_fence() -> None:
    raw, error = accept_output('```json\n{"answer": "north"}\n```', SCHEMA)
    assert error is None
    assert raw == '{"answer":"north"}'
    assert not raw.startswith("```")


def test_provider_error_is_redacted_and_the_body_sends_max_tokens() -> None:
    body = chat_completion_body(
        model="Qwen/Qwen3-32B",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=40960,
        model_limit=1024,
    )
    assert body["max_tokens"] == 1024
    hidden = redact_provider_error(b'{"error":"bad","api_key":"sk-secretvalue"}')
    assert "sk-secretvalue" not in hidden
    assert "[redacted]" in hidden


def test_a_file_id_resolves_to_the_library_document() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    document_id = uuid.uuid4()
    file_id = uuid.uuid4()
    digest = "abc123"
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "content_hash": digest,
        "status": "ready",
        "title": "Policy",
        "passages": [{"text": "Break-glass access is logged."}],
    }
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "sha256": digest,
        "name": "policy.txt",
    }
    found = DocumentLibrary(store)._own(
        type("Actor", (), {"tenant_id": tenant, "user_id": user})(),
        file_id,
    )
    assert found["id"] == document_id


def test_conversation_files_collapse_the_same_bytes() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    conversation_id = uuid.UUID(str(conversation["id"]))
    for _index in range(2):
        file_id = uuid.uuid4()
        store.files[file_id] = {
            "id": file_id,
            "tenant_id": tenant,
            "owner_user_id": user,
            "conversation_id": conversation_id,
            "kind": "artifact",
            "name": "brief.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size_bytes": 12,
            "sha256": "same-bytes",
            "status": "ready",
            "created_at": "t",
        }
    listed = store.list_files(tenant, user, conversation_id=conversation_id)
    assert len([row for row in listed if row.get("name") == "brief.docx"]) == 1


def test_token_bounds_and_key_fallbacks(monkeypatch) -> None:
    from ar_domain.models.request import default_max_output_tokens, model_output_limit

    monkeypatch.delenv("AR_LLM_MAX_TOKENS", raising=False)
    assert default_max_output_tokens() == 1024
    monkeypatch.setenv("AR_LLM_MAX_TOKENS", "nope")
    assert default_max_output_tokens() == 1024
    monkeypatch.setenv("AR_LLM_MAX_TOKENS", "0")
    assert default_max_output_tokens() == 1024
    monkeypatch.setenv("AR_LLM_MAX_TOKENS", "400")
    assert default_max_output_tokens() == 400
    assert model_output_limit({"max_output_tokens": 200}) == 200
    assert model_output_limit({"max_output_tokens": True}) is None
    assert model_output_limit(object()) is None
    bare = tool_call_idempotency_key(run_id="run")
    indexed = tool_call_idempotency_key(run_id="run", call_index=2)
    assert bare.endswith(":call")
    assert indexed.endswith(":i2")


def test_a_second_chart_with_the_same_bytes_is_one_file() -> None:
    store = demo_store()
    version = _version(store, "general.chart")
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Draw it", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    base = {
        "tenant_id": tenant,
        "user_id": user,
        "run_id": run_id,
        "agent_id": store.runs[run_id]["agent_id"],
        "agent_version_id": store.runs[run_id].get("agent_version_id"),
        "tool_version_id": version["id"],
        "arguments": {
            "kind": "bar",
            "title": "Regions",
            "xKey": "region",
            "yKey": "count",
            "rows": [{"region": "North", "count": 2}, {"region": "South", "count": 5}],
        },
    }
    pipeline = ToolPipeline(store)
    assert pipeline.execute({**base, "model_call_id": "one"})["status"] == "succeeded"
    assert pipeline.execute({**base, "model_call_id": "two"})["status"] == "succeeded"
    charts = [row for row in store.files.values() if str(row.get("name")) == "chart.png"]
    assert len(charts) == 1


def test_writer_updates_an_unfinished_row_and_adopts_a_race() -> None:
    from sqlalchemy.exc import IntegrityError

    from ar_domain.durable.m28 import _first_mapping, save_tool_calls

    tenant = uuid.uuid4()
    run_id = uuid.uuid4()
    stored = uuid.uuid4()
    fresh = uuid.uuid4()

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def first(self) -> dict[str, object] | None:
            return self._rows[0] if self._rows else None

        def mappings(self) -> object:
            return self

    class Nested:
        async def __aenter__(self) -> object:
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

    class Session:
        def __init__(self) -> None:
            self.sql: list[str] = []
            self.lookups = 0

        def begin_nested(self) -> Nested:
            return Nested()

        async def execute(self, statement: object, params: object = None) -> Result:
            del params
            sql = str(statement)
            self.sql.append(sql)
            if "FROM runs" in sql:
                return Result([{"id": run_id}])
            if "FROM tool_calls" in sql:
                self.lookups += 1
                if self.lookups == 1:
                    return Result([])
                return Result([{"id": stored, "status": "succeeded"}])
            if "INSERT" in sql:
                raise IntegrityError("dup", {}, Exception("dup"))
            return Result([])

    session = Session()
    adopted = asyncio.run(
        save_tool_calls(
            session,  # type: ignore[arg-type]
            [
                {
                    "id": fresh,
                    "tenant_id": tenant,
                    "run_id": run_id,
                    "idempotency_key": "same",
                    "status": "succeeded",
                }
            ],
        )
    )
    assert adopted[fresh] == stored
    running = uuid.uuid4()
    session.lookups = 0

    class UpdateSession(Session):
        async def execute(self, statement: object, params: object = None) -> Result:
            del params
            sql = str(statement)
            self.sql.append(sql)
            if "FROM runs" in sql:
                return Result([{"id": run_id}])
            if "FROM tool_calls" in sql:
                return Result([{"id": stored, "status": "running"}])
            return Result([])

    updater = UpdateSession()
    adopted_update = asyncio.run(
        save_tool_calls(
            updater,  # type: ignore[arg-type]
            [
                {
                    "id": running,
                    "tenant_id": tenant,
                    "run_id": run_id,
                    "idempotency_key": "same",
                    "status": "running",
                }
            ],
        )
    )
    assert adopted_update[running] == stored
    assert any("UPDATE tool_calls" in sql for sql in updater.sql)
    assert _first_mapping(Result([])) is None


def test_attachment_line_includes_the_document_and_an_excerpt() -> None:
    from ar_domain.files.attachments import conversation_attachments

    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    conversation_id = uuid.UUID(str(conversation["id"]))
    document_id = uuid.uuid4()
    file_id = uuid.uuid4()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "content_hash": "digest",
        "status": "ready",
        "passages": [{"text": "Break-glass access is logged."}],
    }
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "name": "policy.txt",
        "mime_type": "text/plain",
        "size_bytes": 12,
        "sha256": "digest",
    }
    message_id = uuid.uuid4()
    store.messages[message_id] = {
        "id": message_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "role": "user",
        "is_active_branch": True,
        "created_at": "t",
        "content": [{"type": "file", "file_id": str(file_id)}],
    }
    rows = conversation_attachments(store, conversation_id)
    assert rows[0].document_id == document_id
    assert "Break-glass" in rows[0].line()
    assert "documentId=" in rows[0].line()


def test_reload_helpers_merge_calls_and_documents() -> None:
    from ar_domain.durable.hydrate import _library_for_files, _tool_calls_for

    tenant = uuid.uuid4()
    run_id = uuid.uuid4()
    call_id = uuid.uuid4()
    document_id = uuid.uuid4()

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def mappings(self) -> list[dict[str, object]]:
            return self._rows

    class Session:
        async def execute(self, statement: object, params: object = None) -> Result:
            del params
            sql = str(statement)
            if "tool_calls" in sql:
                return Result(
                    [{"id": call_id, "tenant_id": tenant, "idempotency_key": "k", "status": "ok"}]
                )
            return Result(
                [
                    {
                        "id": document_id,
                        "tenant_id": tenant,
                        "content_hash": "digest",
                        "metadata": "{}",
                        "passages": [],
                        "tables": [],
                    }
                ]
            )

    store = demo_store()
    store.files[uuid.uuid4()] = {"tenant_id": tenant, "sha256": "digest"}
    asyncio.run(_tool_calls_for(Session(), store, tenant, run_id))  # type: ignore[arg-type]
    asyncio.run(_library_for_files(Session(), store, tenant))  # type: ignore[arg-type]
    assert call_id in store.tool_calls
    assert document_id in store.library_documents


def test_chart_parts_are_image_content() -> None:
    from ar_domain.tools.agent_loop import _artifact_parts

    file_id = uuid.uuid4()
    store = demo_store()
    store.files[file_id] = {"name": "chart.png", "mime_type": "image/png"}
    parts = _artifact_parts(
        store,
        [{"presentation": {"files": [{"file_id": str(file_id), "name": "chart.png"}]}}],
    )
    assert parts == [
        {
            "type": "image",
            "file_id": str(file_id),
            "name": "chart.png",
            "mime_type": "image/png",
        }
    ]


def _version(store: object, qualified: str) -> dict[str, object]:
    versions = getattr(store, "tool_versions", {})
    for row in versions.values():
        if isinstance(row, dict) and row.get("qualified_name") == qualified:
            return row
    raise AssertionError(f"{qualified} is not seeded")
