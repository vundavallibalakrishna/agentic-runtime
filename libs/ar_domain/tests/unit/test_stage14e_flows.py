"""The flows the certification failed: structured output, citations and approval. Proof: unit."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ar_domain.chat.service import demo_id
from ar_testing.demo import demo_store

_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"capital": {"type": "string"}},
    "required": ["capital"],
    "additionalProperties": False,
}


def _turn(text: str) -> dict[str, object]:
    return {
        "text": text,
        "tool_calls": [],
        "usage": {"tokens_in": 1, "tokens_out": 1},
        "real": True,
    }


def _structured_run(
    replies: list[str],
) -> tuple[Any, dict[str, object], list[list[dict[str, object]]]]:
    """Run one turn that asks for ``_SCHEMA`` against the given model replies."""
    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("model", {}, 5.0, True)
    seen: list[list[dict[str, object]]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del tools, tenant_id, model_alias
        seen.append([dict(message) for message in messages])
        return _turn(replies.pop(0))

    store.complete_turn = complete
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "What is the capital of France?",
        schedule=False,
        response_format=_SCHEMA,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "What is the capital of France?", []))
    return store, store.runs[run_id], seen


def _answer(store: Any, run: dict[str, object]) -> str:
    rows = [
        row
        for row in store.messages.values()
        if row.get("run_id") == run["id"] and row.get("role") == "assistant"
    ]
    return str(rows[-1].get("text") or "") if rows else ""


def test_the_model_is_told_the_schema_the_caller_asked_for() -> None:
    store, run, seen = _structured_run(['{"capital": "Paris"}'])
    assert run["status"] == "completed"
    assert _answer(store, run) == '{"capital":"Paris"}'
    told = " ".join(str(message.get("content") or "") for message in seen[0])
    assert "Return only JSON matching this schema" in told
    assert '"capital"' in told


def test_a_reply_that_misses_the_schema_is_sent_back_with_the_schema() -> None:
    wrong = '{"name": "session__search", "arguments": {"query": "capital of France"}}'
    store, run, seen = _structured_run([wrong, '{"capital": "Paris"}'])
    assert run["status"] == "completed"
    assert _answer(store, run) == '{"capital":"Paris"}'
    retry = str(seen[1][-1].get("content") or "")
    assert "not a tool call written as text" in retry
    assert '"capital"' in retry


def test_a_reply_that_never_matches_is_not_stored_as_the_answer() -> None:
    wrong = '{"name": "session__search", "arguments": {}}'
    store, run, _seen = _structured_run([wrong, wrong])
    assert run["status"] == "failed"
    assert run["error"]["code"] == "repair_exhausted"
    assert "session__search" not in _answer(store, run)


_POLICY = (
    "# Access control policy\n\n"
    "## Break-glass access\n\n"
    "Break-glass access is allowed for 4 hours and must be approved by the duty manager.\n\n"
    "## Retention\n\n"
    "Access logs are kept for 7 years.\n"
)


def _attached_turn(reply: str) -> tuple[Any, dict[str, object], list[dict[str, object]]]:
    """One turn over an attached policy file. Returns the store, the run and the prompt."""
    from ar_domain.agents.access import Actor
    from ar_domain.documents.library import ingest_bytes
    from ar_domain.identity.permissions import PERMISSION_KEYS

    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("model", {}, 5.0, True)
    tenant, user = demo_id("tenant"), demo_id("admin")
    upload = store.upload(tenant, user, "access-policy.md", "text/markdown", _POLICY.encode())
    asyncio.run(
        ingest_bytes(
            store,
            Actor(tenant, user, PERMISSION_KEYS),
            data=_POLICY.encode(),
            filename="access-policy.md",
            media_type="text/markdown",
        )
    )
    seen: list[dict[str, object]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del tools, tenant_id, model_alias
        seen.extend(dict(message) for message in messages)
        return _turn(reply)

    store.complete_turn = complete
    conversation = store.create_conversation(tenant, user, None)
    question = "How long is break-glass access allowed? Cite the passage."
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        question,
        schedule=False,
        attachment_ids=[uuid.UUID(str(upload["id"]))],
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, question, []))
    return store, store.runs[run_id], seen


def _assistant(store: Any, run: dict[str, object]) -> dict[str, object]:
    return next(
        row
        for row in store.messages.values()
        if row.get("run_id") == run["id"] and row.get("role") == "assistant"
    )


def test_an_attached_passage_is_shown_with_its_anchor_and_cited_as_a_part() -> None:
    store, run, seen = _attached_turn("Break-glass access is allowed for 4 hours [p1-s0 p.1].")
    prompt = " ".join(str(message.get("content") or "") for message in seen)
    # The model sees each passage after its anchor, and is told to cite it.
    assert "[p1-s0 p.1] Break-glass access is allowed for 4 hours" in prompt
    assert "put that anchor after the statement" in prompt
    assert run["status"] == "completed"
    cited = [part for part in _assistant(store, run)["content"] if part["type"] == "citation_ref"]
    assert len(cited) == 1
    citation = cited[0]["citation"]
    assert citation["anchor"] == "p1-s0"
    assert citation["source_kind"] == "document"
    assert "duty manager" in citation["snippet"]
    assert citation["uri"].endswith("#p1-s0")
    added = [event for event in store.events[run["id"]] if event["type"] == "citation.added"]
    assert added


def test_an_anchor_no_attached_document_holds_is_not_a_citation() -> None:
    store, run, _seen = _attached_turn("It is allowed for 4 hours [p9-s9 p.9].")
    parts = _assistant(store, run)["content"]
    assert [part["type"] for part in parts] == ["text"]


def test_what_a_run_waits_on_survives_being_stored_and_read_by_another_process() -> None:
    import orjson

    from ar_domain.approvals.pending import amend, held, hold, release

    approval, version = uuid.uuid4(), uuid.uuid4()
    run: dict[str, object] = {"id": uuid.uuid4(), "checkpoint": {"worker_loop": {"steps": 2}}}
    hold(run, {"approval_id": approval, "tool_version_id": version, "arguments": {"path": "a.txt"}})
    # The checkpoint is stored as JSON. Another process reads it back with no object ids.
    other = {"checkpoint": orjson.loads(orjson.dumps(run["checkpoint"]))}
    pending = held(other)
    assert pending is not None
    assert pending["approval_id"] == approval
    assert pending["tool_version_id"] == version
    assert pending["arguments"] == {"path": "a.txt"}
    amend(other, args_hash="h2")
    assert (held(other) or {})["args_hash"] == "h2"
    release(other)
    assert held(other) is None
    # The rest of the checkpoint is untouched.
    assert other["checkpoint"] == {"worker_loop": {"steps": 2}}
    assert held({"status": "running"}) is None


def test_a_step_for_another_process_waits_for_the_commit() -> None:
    from types import SimpleNamespace

    from ar_domain.durable.after import after_commit, run_after_commit

    ran: list[str] = []
    # A store with nothing to commit runs the step at once.
    after_commit(SimpleNamespace(), lambda: ran.append("now"))
    assert ran == ["now"]
    # A unit of the read model holds it until its rows are committed.
    unit = SimpleNamespace(after_commit=[])
    after_commit(unit, lambda: ran.append("first"))
    after_commit(unit, lambda: ran.append("second"))
    assert ran == ["now"]
    run_after_commit(unit)
    assert ran == ["now", "first", "second"]
    assert unit.after_commit == []


def test_the_image_tool_refuses_in_words_before_it_asks_a_model() -> None:
    from ar_domain.tools.vision import _vision_alias, dispatch_image

    store = demo_store()
    who = {"_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin")}
    assert dispatch_image(store, "describe", who)["code"] == "unknown_tool"
    assert dispatch_image(store, "ask", {"question": "What is it?"})["code"] == "validation_failed"
    assert "question is required" in dispatch_image(store, "ask", who)["text"]
    missing = dispatch_image(
        store, "ask", {"question": "What?", "file_id": str(uuid.uuid4()), **who}
    )
    assert missing["is_error"] is True
    # The alias comes from the call, then from the agent, then the install's default.
    assert _vision_alias(store, {"vision_alias": "eyes"}) == "eyes"
    version_id = uuid.uuid4()
    store.versions[version_id] = {"definition": {"model": {"vision_alias": "agent-eyes"}}}
    assert _vision_alias(store, {"_agent_version_id": version_id}) == "agent-eyes"
    assert _vision_alias(store, {}) == "vision"


def test_research_tools_refuse_bad_input_in_words() -> None:
    from ar_domain.research.handlers import dispatch_context, dispatch_research

    store = demo_store()
    tenant = demo_id("tenant")
    assert dispatch_research(store, "fetch", {"_tenant_id": tenant})["code"] == "validation_failed"
    wrong = dispatch_research(store, "fetch", {"url": "ftp://example.com/a", "_tenant_id": tenant})
    assert "http or https" in wrong["text"]
    assert dispatch_context(store, "retrieve", {})["code"] == "validation_failed"
    no_run = dispatch_context(store, "retrieve", {"output_id": "o1", "_run_id": "not-a-run"})
    assert no_run["code"] == "not_found"
    run_id = uuid.uuid4()
    store.runs[run_id] = {"id": run_id, "tenant_id": tenant}
    absent = dispatch_context(store, "retrieve", {"output_id": "o1", "_run_id": str(run_id)})
    assert "not stored on this run" in absent["text"]


def test_an_approved_call_that_fails_ends_the_run_with_the_reason(
    monkeypatch: object,
) -> None:
    from ar_domain.approvals.pending import held, hold
    from ar_domain.tools import resume

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "write it", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    approval_id = uuid.uuid4()
    run["status"] = "waiting_approval"
    hold(run, {"approval_id": approval_id, "tool_version_id": uuid.uuid4(), "arguments": {}})
    refused = {"status": "failed", "error": {"message": "the folder is read-only"}}
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "ar_domain.tools.gateway_client.execute_tool", lambda _store, _request: refused
    )
    # An approval for another call leaves the run waiting.
    resume.settle_approval(store, {"id": uuid.uuid4(), "run_id": run["id"], "status": "approved"})
    assert run["status"] == "waiting_approval"
    resume.settle_approval(store, {"id": approval_id, "run_id": run["id"], "status": "approved"})
    assert run["status"] == "completed"
    assert "did not run: the folder is read-only" in str(run["result_summary"])
    assert held(run) is None


def test_a_rejected_approval_ends_the_run_and_says_so() -> None:
    from ar_domain.approvals.pending import hold
    from ar_domain.tools import resume

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "write it", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    approval_id = uuid.uuid4()
    run["status"] = "waiting_approval"
    hold(run, {"approval_id": approval_id, "model_call_id": uuid.uuid4()})
    resume.settle_approval(store, {"id": approval_id, "run_id": run["id"], "status": "rejected"})
    assert run["status"] == "completed"
    assert "rejected" in str(run["result_summary"])
    # A run that is no longer active is left alone.
    resume.settle_approval(store, {"id": approval_id, "run_id": run["id"], "status": "expired"})
    assert "rejected" in str(run["result_summary"])
    resume.settle_approval(store, {"id": approval_id, "run_id": "not-a-run", "status": "approved"})


def test_a_chart_row_written_as_name_to_number_keeps_its_name() -> None:
    from ar_domain.tools.charts import _rows

    # What a model sent for "North 12, South 19": the key is the label.
    named = _rows(
        {"rows": [{"North": 12}, {"South": 19}], "xKey": "region", "yKey": "count", "kind": "bar"}
    )
    assert named == [("North", 12.0), ("South", 19.0)]
    # The usual shapes are unchanged.
    assert _rows({"rows": [{"region": "East", "count": 7}], "xKey": "region", "yKey": "count"}) == [
        ("East", 7.0)
    ]
    assert _rows({"rows": [{"label": "West", "value": 15}]}) == [("West", 15.0)]
    assert _rows({"rows": [["A", 1], 5]}) == [("A", 1.0), ("1", 5.0)]


def test_the_runtimes_plan_is_settled_when_the_run_ends() -> None:
    from ar_domain.loop.planning import end_tool_plan

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    row = store.conversations[uuid.UUID(str(conversation["id"]))]
    posted = store.post_message(tenant, user, row["id"], "chart it", schedule=False)
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    row["plan"] = [
        {"id": "1", "title": "general.chart", "status": "in_progress", "auto": True},
        {"id": "2", "title": "Write the summary", "status": "in_progress"},
    ]
    end_tool_plan(store, run, "done")
    # The step the runtime wrote is finished. A step the model wrote is the model's to move.
    assert [item["status"] for item in row["plan"]] == ["done", "in_progress"]
    updates = [event for event in store.events[run["id"]] if event["type"] == "plan.updated"]
    assert updates[-1]["data"]["items"][0]["status"] == "done"
    # Nothing left to settle: no second event.
    end_tool_plan(store, run, "done")
    assert len([e for e in store.events[run["id"]] if e["type"] == "plan.updated"]) == len(updates)


def test_a_failed_run_does_not_leave_its_plan_in_progress() -> None:
    from ar_domain.runs.failure import fail_run

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    row = store.conversations[uuid.UUID(str(conversation["id"]))]
    posted = store.post_message(tenant, user, row["id"], "delete it", schedule=False)
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    row["plan"] = [
        {"id": "1", "title": "petstore.delete_pet", "status": "in_progress", "auto": True}
    ]
    fail_run(store, run, code="tool_failed", message="A tool call failed.")
    assert row["plan"][0]["status"] == "cancelled"


def test_a_report_lists_a_text_once_and_names_documents_without_addresses() -> None:
    from ar_domain.research.engine import _collect, synthesise

    same = "Break-glass access is allowed for 4 hours and must be approved by the duty manager."
    state: dict[str, object] = {
        "question": "Who approves break-glass access?",
        "queries": [],
        "subtasks": {
            "1": {
                "status": "done",
                "sources": [
                    {"url": "library://a#p1-s0", "title": "Break-glass access", "text": same},
                    {"url": "library://b#p1-s0", "title": "Break-glass access", "text": same},
                    {
                        "url": "https://example.com/policy",
                        "title": "Policy",
                        "text": "Logs are kept for 7 years.",
                    },
                ],
            }
        },
    }
    _collect(state, {"checkpoint": {"research": state}})
    sources = state["sources"]
    assert isinstance(sources, list)
    # Two copies of one document are one source.
    assert [row["url"] for row in sources] == ["library://a#p1-s0", "https://example.com/policy"]
    report = synthesise("Who approves break-glass access?", sources)
    assert "library://" not in report
    assert "[1] Break-glass access" in report
    assert "[2] Policy https://example.com/policy" in report


def test_web_search_is_offered_only_when_the_tenant_has_a_provider() -> None:
    from ar_domain.agents.access import Actor
    from ar_domain.agents.service import AgentLifecycle
    from ar_domain.identity.permissions import PERMISSION_KEYS
    from ar_domain.tools.pipeline import ToolPipeline
    from ar_domain.tools.readiness import ready_for

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    actor = Actor(tenant, user, PERMISSION_KEYS, display_name="Dev Admin")
    life = AgentLifecycle(store)
    made = life.create(actor, slug="searcher", name="Searcher", template="blank")
    agent_id = uuid.UUID(str(made["id"]))
    life.save_draft(
        actor,
        agent_id,
        {"instructions": "work", "tools": [{"server": "general", "include": ["search", "chart"]}]},
    )
    version_id = uuid.UUID(
        str(life.publish(actor, agent_id, change_note="x")["published_version_id"])
    )

    def offered() -> set[str]:
        rows = ToolPipeline(store).resolve_catalog(agent_version_id=version_id, user_id=user)[
            "tools"
        ]
        return {str(row["qualified_name"]) for row in rows}

    # No provider: the model is not offered a tool that can only refuse.
    assert not ready_for(store, tenant, "general.search")
    assert offered() == {"general.chart"}

    class _Provider:
        def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
            del query, limit
            return []

    store.search_provider = _Provider()
    assert ready_for(store, tenant, "general.search")
    assert offered() == {"general.chart", "general.search"}
    assert ready_for(store, tenant, "general.chart")
