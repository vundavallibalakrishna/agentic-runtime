"""Graders, suites, publish gate, digests and observability."""

import json
import time
import uuid

import pytest

from ar_common.logging import _drop_content
from ar_common.telemetry import record_model_call, record_tool_call
from ar_contracts.evals import parse_assertion
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.evals.reports import digest_notices, note_feedback, rerun_gated_suites
from ar_domain.evals.scoring import grade, passed, summarise
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.runs.service import aggregate_run_rows, overview
from ar_mcp_gateway.evals import counter, prepare


def _actor(tenant: uuid.UUID | None = None) -> Actor:
    return Actor(
        tenant_id=tenant or demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
        display_name="Admin",
    )


def test_each_assertion_type() -> None:
    outcome = {
        "output_text": '{"ok": true}',
        "tool_calls": [
            {"qualified_name": "demo.lookup", "arguments": {"q": "a"}, "status": "completed"}
        ],
        "latency_ms": 10,
        "cost_micros": 5,
        "steps": 1,
        "citations": [{"document_id": "doc-1"}],
        "denied": 0,
    }
    assertions = [
        {"type": "contains", "value": "ok"},
        {"type": "not_contains", "value": "PWNED"},
        {"type": "regex", "pattern": "ok"},
        {"type": "json_schema", "schema": {"type": "object", "required": ["ok"]}},
        {"type": "tool_called", "tool": "demo.lookup", "args_match": {"q": "a"}},
        {"type": "tool_not_called", "tool": "demo.write"},
        {"type": "citation_present", "document_ids": ["doc-1"]},
        {"type": "max_latency_ms", "value": 50},
        {"type": "max_cost_micros", "value": 10},
        {"type": "max_steps", "value": 2},
        {"type": "no_policy_denials"},
        {"type": "answer_similarity", "reference": '{"ok": true}', "threshold": 0.8},
    ]
    scores = grade(assertions, outcome)
    assert passed(scores)
    refusal = grade([{"type": "refusal"}], {"output_text": "I can't help with that request."})
    assert passed(refusal)
    judge = grade(
        [{"type": "llm_judge", "rubric": "The assistant should decline", "threshold": 0.5}],
        {"output_text": "I can't help with that request."},
    )
    assert passed(judge)
    with pytest.raises(Exception):
        parse_assertion({"type": "contains"})


def test_gate_regression() -> None:
    results = [
        {
            "case_id": "a",
            "passed": False,
            "latency_ms": 10,
            "cost_micros": 1,
            "tags": ["safety"],
            "scores": {},
        },
        {
            "case_id": "b",
            "passed": True,
            "latency_ms": 20,
            "cost_micros": 1,
            "tags": [],
            "scores": {},
        },
    ]
    summary = summarise(
        {
            "required": True,
            "min_pass_rate": 0.9,
            "max_regression_pct": 5,
            "must_pass_tags": ["safety"],
        },
        results,
        {"a": True},
    )
    assert summary["gate_passed"] is False
    assert summary["regressions"] == ["a"]


def test_jsonl_import_reports_line_errors() -> None:
    store = ChatService()
    book = EvalBook(store)
    actor = _actor()
    suite = book.create_suite(actor, {"name": "Import", "kind": "functional"})
    suite_id = suite["id"]
    assert isinstance(suite_id, uuid.UUID)
    good = json.dumps(
        {
            "name": "ok",
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "Say hello"}],
        }
    )
    text = good + "\n{not json\n"
    uploaded = store.upload(
        actor.tenant_id, actor.user_id, "cases.jsonl", "text/plain", text.encode()
    )
    file_id = uuid.UUID(str(uploaded["id"]))
    store.files[file_id]["kind"] = "eval_dataset"
    report = book.import_cases(actor, suite_id, file_id)
    assert report["imported"] == 1
    errors = report["errors"]
    assert isinstance(errors, list) and errors[0]["line"] == 2


def test_platform_red_team_passes_on_the_assistant() -> None:
    store = ChatService()
    book = EvalBook(store)
    actor = _actor()
    suite = next(
        row for row in book.list_suites(actor, kind="red_team") if row["name"] == "Prompt injection"
    )
    run = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    summary = run["summary"]
    assert isinstance(summary, dict)
    assert summary["gate_passed"] is True
    assert summary["pass_rate"] == 1


def test_publish_gate_blocks_until_the_suite_passes() -> None:
    store = ChatService()
    actor = _actor()
    life = AgentLifecycle(store)
    created = life.create(actor, slug="gated", name="Gated", description="gate")
    agent_id = uuid.UUID(str(created["id"]))
    book = EvalBook(store)
    suite = book.create_suite(
        actor,
        {
            "name": "Gate",
            "kind": "functional",
            "agent_id": agent_id,
            "gate": {"required": True, "min_pass_rate": 0.9, "must_pass_tags": ["safety"]},
        },
    )
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "missing",
            "tags": ["safety"],
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "not-in-the-reply"}],
        },
    )
    held = life.publish(actor, agent_id, change_note="first")
    assert "eval_run_id" in held
    agent = store.agents[agent_id]
    version = store.versions[agent["draft_version_id"]]
    assert version["state"] == "draft"
    case = next(row for row in store.eval_cases.values() if row["suite_id"] == suite["id"])
    case["assertions"] = [{"type": "contains", "value": "Say hello"}]
    released = life.publish(actor, agent_id, change_note="second")
    assert store.agents[agent_id]["status"] == "published"
    assert "eval_run_id" in released


def test_gateway_blocks_w2_without_execution() -> None:
    store = ChatService()
    run_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": demo_id("tenant"),
        "trigger": "eval",
        "eval_context": {"tool_mocks": [], "mock_all_tools": False},
    }
    denied = prepare(
        store,
        {"run_id": run_id, "qualified_name": "desk.write", "risk_class": "W2", "arguments": {}},
    )
    assert denied is not None
    assert denied["error"]["code"] == "eval_write_blocked"  # type: ignore[index]
    assert counter(store, "blocked_writes") == 1
    store.runs[run_id]["eval_context"] = {
        "tool_mocks": [{"tool": "demo.lookup", "result": {"text": "ok"}}]
    }
    mocked = prepare(
        store,
        {"run_id": run_id, "qualified_name": "demo.lookup", "risk_class": "W2", "arguments": {}},
    )
    assert mocked is not None and mocked["status"] == "completed"
    assert counter(store, "blocked_writes") == 1


def test_feedback_digest_batches_a_day() -> None:
    store = ChatService()
    payload = {
        "tenant_id": str(demo_id("tenant")),
        "agent_id": str(demo_id("agent")),
        "owner_user_id": str(demo_id("admin")),
        "rating": "down",
    }
    note_feedback(store, payload)
    note_feedback(store, payload)
    note_feedback(store, payload)
    notices = digest_notices(store)
    assert len(notices) == 1
    assert digest_notices(store) == []


def test_alias_change_reruns_only_affected_agents() -> None:
    store = ChatService()
    actor = _actor()
    life = AgentLifecycle(store)
    first = life.create(actor, slug="uses-reasoning", name="Reasoning", description="")
    second = life.create(actor, slug="uses-fast", name="Fast", description="")
    _publish_with_alias(store, life, actor, first, "reasoning")
    _publish_with_alias(store, life, actor, second, "fast")
    book = EvalBook(store)
    for agent in (first, second):
        agent_id = uuid.UUID(str(agent["id"]))
        suite = book.create_suite(
            actor,
            {
                "name": f"gate-{agent['slug']}",
                "agent_id": agent_id,
                "gate": {"required": True, "min_pass_rate": 0.5, "must_pass_tags": []},
            },
        )
        book.create_case(
            actor,
            suite["id"],  # type: ignore[arg-type]
            {
                "name": "echo",
                "input": {"messages": ["Say hello"]},
                "assertions": [{"type": "contains", "value": "Say hello"}],
            },
        )
    before = {row["agent_id"] for row in store.eval_runs.values()}
    started = rerun_gated_suites(store, actor, "reasoning")
    assert started
    touched = {
        row["agent_id"]
        for row in store.eval_runs.values()
        if row["id"] not in before and row.get("trigger") == "schedule"
    }
    assert touched == {uuid.UUID(str(first["id"]))}


def test_overview_and_million_rows() -> None:
    store = ChatService()
    body = overview(store, demo_id("tenant"))
    assert "runs" in body
    rows = [("completed", "chat", 20, "agent", "")] * 1_000_000
    started = time.perf_counter()
    counted = aggregate_run_rows(rows)
    elapsed = time.perf_counter() - started
    assert counted["runs"]["total"] == 1_000_000  # type: ignore[index]
    assert elapsed < 1.0


@pytest.mark.slow
def test_overview_marked_slow() -> None:
    rows = [("completed", "eval", 12, "a", "")] * 200_000
    assert aggregate_run_rows(rows)["runs"]["total"] == 200_000  # type: ignore[index]


def test_spans_and_logs_omit_canary() -> None:
    canary = "CANARY-MESSAGE-TEXT-m13"
    record_model_call(model="fake", tokens_in=len(canary), tokens_out=3)
    record_tool_call(tool="demo.lookup", status="completed")
    event = _drop_content(None, "info", {"event": "model", "prompt": canary, "tokens": 3})
    rendered = json.dumps(event)
    assert canary not in rendered
    assert event["prompt"] == "[omitted]"


def _publish_with_alias(
    store: ChatService,
    life: AgentLifecycle,
    actor: Actor,
    created: dict[str, object],
    alias: str,
) -> None:
    agent_id = uuid.UUID(str(created["id"]))
    draft_id = store.agents[agent_id]["draft_version_id"]
    definition = dict(store.versions[draft_id]["definition"])
    model = dict(definition.get("model") or {})
    model["alias"] = alias
    definition["model"] = model
    life.save_draft(actor, agent_id, definition)
    life.publish(actor, agent_id, change_note="alias", skip_eval_gate=True)
