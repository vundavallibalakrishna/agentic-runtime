"""Cover eval catalogue, gateway, traces and the offline eval CLI."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from ar_common.errors import ArError, NotFoundError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.evals.book import EvalBook, _documents, public_row
from ar_domain.evals.seed_suites import suite_root
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.runs.health import _probe
from ar_domain.runs.service import overview, trace_links
from ar_mcp_gateway.evals import counter, prepare
from ar_runtime.langfuse import trace_payload
from ar_system.evals.cli import main
from ar_system.evals.graders import JUDGE_PROMPT, grade
from ar_system.evals.judge import judge_prompt


def _actor(**extra: object) -> Actor:
    values: dict[str, object] = {
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "permissions": PERMISSION_KEYS,
    }
    values.update(extra)
    return Actor(**values)  # type: ignore[arg-type]


def test_suite_catalogue_edges() -> None:
    store = ChatService()
    book = EvalBook(store)
    actor = _actor()
    with pytest.raises(ValidationFailedError):
        book.create_suite(actor, {"name": "  "})
    with pytest.raises(ValidationFailedError):
        book.create_suite(actor, {"name": "Bad", "kind": "nope"})
    suite = book.create_suite(actor, {"name": "Edges", "description": "d", "kind": "safety"})
    suite_id = suite["id"]
    assert isinstance(suite_id, uuid.UUID)
    with pytest.raises(ArError):
        book.create_suite(actor, {"name": "Edges"})
    with pytest.raises(ValidationFailedError):
        book.update_suite(actor, suite_id, {"name": ""})
    with pytest.raises(ValidationFailedError):
        book.update_suite(actor, suite_id, {"kind": "nope"})
    renamed = book.update_suite(
        actor,
        suite_id,
        {
            "name": "Edges two",
            "description": "more",
            "kind": "retrieval",
            "gate": {"required": False, "min_pass_rate": 0.5, "must_pass_tags": []},
            "agent_id": None,
        },
    )
    assert renamed["name"] == "Edges two"
    with pytest.raises(ValidationFailedError):
        book.create_case(actor, suite_id, {"name": "bad-tags", "tags": "nope"})
    case = book.create_case(
        actor,
        suite_id,
        {
            "name": "one",
            "input": {"messages": ["hello"]},
            "assertions": [{"type": "contains", "value": "hello"}],
            "tags": ["a"],
        },
    )
    case_id = case["id"]
    assert isinstance(case_id, uuid.UUID)
    updated = book.update_case(
        actor,
        suite_id,
        case_id,
        {
            "name": "one-b",
            "input": {"messages": ["hello again"]},
            "assertions": [{"type": "contains", "value": "hello"}],
            "tool_mocks": [{"tool": "demo.lookup", "result": {"text": "ok"}}],
            "tags": ["b"],
        },
    )
    assert updated["name"] == "one-b"
    assert book.list_cases(actor, suite_id)
    other = book.create_suite(actor, {"name": "Other"})
    other_id = other["id"]
    assert isinstance(other_id, uuid.UUID)
    with pytest.raises(NotFoundError):
        book.update_case(actor, other_id, case_id, {"name": "no"})
    with pytest.raises(NotFoundError):
        book.delete_case(actor, other_id, case_id)
    book.delete_case(actor, suite_id, case_id)
    book.delete_suite(actor, suite_id)
    assert suite_id not in store.eval_suites
    with pytest.raises(ValidationFailedError):
        book.create_suite(actor, {"name": "bad-id", "agent_id": "not-a-uuid"})
    assert public_row({"id": suite_id, "when": datetime(2026, 1, 1, tzinfo=UTC), "n": 1})["id"]


def test_import_conversation_run_and_feedback() -> None:
    store = ChatService()
    book = EvalBook(store)
    actor = _actor()
    suite = book.create_suite(actor, {"name": "Import edges"})
    suite_id = suite["id"]
    assert isinstance(suite_id, uuid.UUID)
    missing = uuid.uuid4()
    with pytest.raises(NotFoundError):
        book.import_cases(actor, suite_id, missing)
    uploaded = store.upload(actor.tenant_id, actor.user_id, "notes.txt", "text/plain", b"hello")
    file_id = uuid.UUID(str(uploaded["id"]))
    with pytest.raises(ValidationFailedError):
        book.import_cases(actor, suite_id, file_id)
    store.files[file_id]["kind"] = "eval_dataset"
    store.blobs[file_id] = b"\n"
    empty = book.import_cases(actor, suite_id, file_id)
    assert empty["imported"] == 0
    store.blobs[file_id] = (
        b"cases:\n"
        b"  - name: yaml-one\n"
        b"    input:\n"
        b"      messages: ['Say hello']\n"
        b"    assertions:\n"
        b"      - type: contains\n"
        b"        value: Say hello\n"
        b"  - input:\n"
        b"      messages: ['missing name']\n"
    )
    yaml_report = book.import_cases(actor, suite_id, file_id)
    assert yaml_report["imported"] == 1
    assert yaml_report["errors"]
    store.blobs[file_id] = (
        b"1\n"
        b'{"name": "line", "input": {"messages": ["Say hello"]}, '
        b'"assertions": [{"type": "contains", "value": "Say hello"}]}\n'
    )
    line_report = book.import_cases(actor, suite_id, file_id)
    assert line_report["imported"] == 1
    assert _documents("name: lone\ninput:\n  messages: ['Say hello']")
    assert _documents("- name: listed\n")[0]

    conversation = store.create_conversation(actor.tenant_id, actor.user_id, None)
    conversation_id = uuid.UUID(str(conversation["id"]))
    posted = store.post_message(
        actor.tenant_id, actor.user_id, conversation_id, "Say hello", schedule=False
    )
    message_id = uuid.UUID(str(posted["message"]["id"]))
    message = next(row for row in store.messages.values() if row["id"] == message_id)
    message["content"] = ["Say", "hello"]
    store.set_feedback(actor.tenant_id, actor.user_id, message_id, "down", "too long")
    created = book.case_from_conversation(
        actor, suite_id, {"conversation_id": str(conversation_id), "message_id": str(message_id)}
    )
    assert created["tags"] == ["feedback"]
    with pytest.raises(NotFoundError):
        book.case_from_conversation(
            actor,
            suite_id,
            {"conversation_id": str(conversation_id), "message_id": str(uuid.uuid4())},
        )
    with pytest.raises(ValidationFailedError):
        book.case_from_conversation(actor, suite_id, {"conversation_id": "", "message_id": ""})

    limited = _actor(permissions=frozenset({"evals:run"}))
    with pytest.raises(ArError):
        book.start_run(limited, suite_id, {"model_alias_override": "fast"})
    with pytest.raises(ValidationFailedError):
        book.start_run(actor, suite_id, {"trigger": "nope"})
    store.defer_eval_runs = True
    queued = book.start_run(actor, suite_id, {"trigger": "ci", "agent_version_ref": "1"})
    assert queued["status"] == "queued"
    draft = book.start_run(actor, suite_id, {"agent_version_ref": "draft", "tags": None})
    assert draft["status"] == "queued"
    run_id = queued["id"]
    assert isinstance(run_id, uuid.UUID)
    cancelled = book.cancel(actor, run_id)
    assert cancelled["status"] == "cancelled"
    with pytest.raises(ArError):
        book.cancel(actor, run_id)
    assert book.results(actor, run_id) == []
    assert book.list_runs(actor, suite_id=suite_id, status="cancelled")
    feedback = book.list_feedback(actor)
    assert feedback and feedback[0]["comment"] == "too long"
    member = _actor(user_id=demo_id("member"), permissions=frozenset({"evals:manage"}))
    hidden = book.list_feedback(member)
    assert hidden[0]["comment"] == ""
    assistant = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    assistant["slug"] = "renamed"
    bare = book.create_suite(actor, {"name": "No agent"})
    with pytest.raises(ValidationFailedError):
        book.start_run(actor, bare["id"], {})  # type: ignore[arg-type]
    assistant["slug"] = "assistant"
    with pytest.raises(NotFoundError):
        book.start_run(actor, suite_id, {"agent_version_ref": "99"})
    with pytest.raises(NotFoundError):
        book.get_suite(actor, uuid.uuid4())


def test_gateway_mocks_and_trace_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    store = ChatService()
    assert prepare(store, {"run_id": "nope"}) is None
    run_id = uuid.uuid4()
    version_id = uuid.uuid4()
    store.tool_versions[version_id] = {"qualified_name": "demo.lookup", "risk_class": "W3"}
    store.runs[run_id] = {"id": run_id, "trigger": "chat"}
    assert prepare(store, {"run_id": run_id, "tool_version_id": version_id}) is None
    store.runs[run_id]["eval_context"] = "nope"
    assert prepare(store, {"run_id": run_id}) is None
    store.runs[run_id]["eval_context"] = {
        "tool_mocks": [
            {"tool": "demo.lookup", "match_args": {"q": "a"}, "error": {"message": "boom"}},
        ],
        "mock_all_tools": True,
    }
    missed = prepare(
        store,
        {"run_id": run_id, "tool_version_id": version_id, "arguments": {"q": "a"}},
    )
    assert missed is not None and missed["error"]["code"] == "mock_error"  # type: ignore[index]
    skipped = prepare(
        store,
        {"run_id": run_id, "tool_version_id": version_id, "arguments": "nope"},
    )
    assert skipped is not None and skipped["error"]["code"] == "eval_mock_required"
    store.eval_gateway = {"mocked": "bad"}
    required = prepare(store, {"run_id": run_id, "qualified_name": "other", "arguments": {}})
    assert required is not None and required["error"]["code"] == "eval_mock_required"
    assert counter(store, "mocked") == 1
    store.runs[run_id]["eval_context"] = {"tool_mocks": []}
    del store.eval_gateway
    blocked = prepare(store, {"run_id": run_id, "tool_version_id": version_id})
    assert blocked is not None and blocked["error"]["code"] == "eval_write_blocked"
    allowed = prepare(
        store,
        {"run_id": run_id, "qualified_name": "demo.read", "risk_class": "R0", "arguments": {}},
    )
    assert allowed is None

    monkeypatch.setenv("AR_TRACE_UI_URL", "http://tempo")
    monkeypatch.setenv("AR_LANGFUSE_HOST_PORT", "3001")
    linked = trace_links({"trace_id": "abc", "usage": {"wall_clock_ms": 12}})
    assert "tempo" in str(linked["trace_url"])
    assert linked["langfuse_url"].endswith("/trace/abc")
    payload = trace_payload(
        {
            "id": uuid.uuid4(),
            "model": "fake",
            "tokens_in": 1.5,
            "tokens_out": True,
            "latency_ms": "x",
        },
        capture_content=True,
        output="hello",
    )
    assert payload["output"] == "hello"
    assert payload["tokens_out"] == 0
    assert "score" in JUDGE_PROMPT
    assert grade([{"type": "contains", "value": "a"}], {"output_text": "a"})


def test_overview_windows_and_component_probe() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    start = datetime(2020, 1, 1, tzinfo=UTC)
    end = datetime(2030, 1, 1, tzinfo=UTC)
    run_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "agent_id": agent_id,
        "status": "failed",
        "trigger": "eval",
        "error": "boom",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "usage": {"wall_clock_ms": 40},
    }
    store.tool_calls[uuid.uuid4()] = {
        "tenant_id": tenant,
        "run_id": run_id,
        "qualified_name": "demo.lookup",
        "latency_ms": 8,
        "status": "failed",
    }
    store.approvals[uuid.uuid4()] = {
        "tenant_id": tenant,
        "status": "approved",
        "created_at": datetime(2024, 6, 1, tzinfo=UTC),
    }
    store.feedback[("m", "u")] = {
        "tenant_id": tenant,
        "rating": "up",
        "created_at": datetime(2024, 6, 1, tzinfo=UTC),
    }
    store.feedback[("n", "u")] = {
        "tenant_id": tenant,
        "rating": "down",
        "created_at": "not-a-date",
    }
    store.usage_daily[(str(tenant), "2024-01-01")] = {"cost_micros": 7}
    store.usage_daily[(str(tenant), "2024-01-02")] = 3
    body = overview(store, tenant, start=start, end=end, agent_id=agent_id)
    assert body["cost_micros"] == 10
    assert body["tools"][0]["qualified_name"] == "demo.lookup"
    assert body["approvals"]["approved"] == 1
    assert body["feedback"]["up"] == 1
    assert body["runs"]["total"] == 1

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/down":
            return httpx.Response(503)
        if request.url.path == "/slow":
            raise httpx.ConnectError("refused")
        return httpx.Response(404)

    async def probes() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            down = await _probe(client, "api", "http://example/down")
            missing = await _probe(client, "opa", "http://example/missing")
            refused = await _probe(client, "db", "http://example/slow")
            blank = await _probe(client, "valkey", "")
        assert down["status"] == "down" and down["detail"] == "503"
        assert missing["status"] == "degraded"
        assert refused["status"] == "down"
        assert blank["detail"] == "not configured"

    import asyncio

    asyncio.run(probes())


def test_eval_cli_scores_repository_suites(monkeypatch: pytest.MonkeyPatch) -> None:
    root = suite_root()
    assert root is not None
    assert main(["run", str(root / "golden" / "assistant.yaml")]) == 0
    assert main(["run", str(root / "redteam")]) == 0
    assert main(["run", str(root / "missing.yaml")]) == 1

    def failed(self: EvalBook, actor: Actor, suite_id: uuid.UUID, body: dict[str, object]) -> dict:
        del self, actor, suite_id, body
        return {"summary": {"pass_rate": 0}, "status": "completed"}

    monkeypatch.setattr(EvalBook, "start_run", failed)
    assert main(["run", str(root / "golden")]) == 1


def test_judge_prompt_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_system.evals.judge.Path.is_file", lambda _self: False)
    assert "score" in judge_prompt()
