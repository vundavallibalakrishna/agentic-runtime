"""The llm_judge assertion: a model checks an answer against what it must and must not say."""

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

import orjson
import pytest

from ar_common.errors import ValidationFailedError
from ar_contracts.evals import parse_assertion
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.evals.judge import judge_answer
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_testing.stand_in import StandIn

ANSWER = "Premium cloud lists **16x5** support. The Template option has 8x5."
MUST = ["The Premium cloud option lists 16x5 support."]
MUST_NOT = ["Says 24x7 support is available."]


def _replies(table: dict[str, dict[str, str]]) -> Callable[[str, str], str | None]:
    """A judge that answers each statement from ``table``, keyed by a word in it."""

    def ask(task: str, evidence: str) -> str | None:
        del evidence
        for word, reply in table.items():
            if word in task:
                return orjson.dumps(reply).decode()
        return None

    return ask


def test_an_answer_that_states_every_fact_and_no_forbidden_claim_passes() -> None:
    ask = _replies(
        {
            "16x5": {"verdict": "stated", "quote": "Premium cloud lists 16x5 support."},
            "24x7": {"verdict": "not_stated", "quote": ""},
        }
    )
    result = judge_answer(ANSWER, MUST, MUST_NOT, ask, model_id="m1")
    assert result["passed"] is True
    assert result["score"] == 1.0
    items = result["items"]
    assert isinstance(items, list)
    assert {item["kind"] for item in items} == {"must", "must_not"}
    assert all(item["model_id"] == "m1" and item["prompt_hash"] for item in items)


def test_a_quote_the_answer_does_not_contain_is_not_a_stated_fact() -> None:
    ask = _replies(
        {
            "16x5": {"verdict": "stated", "quote": "Premium includes round-the-clock help."},
            "24x7": {"verdict": "not_stated", "quote": ""},
        }
    )
    result = judge_answer(ANSWER, MUST, MUST_NOT, ask, model_id="m1")
    assert result["passed"] is False
    first = result["items"][0]  # type: ignore[index]
    assert first["verdict"] == "not_stated"
    assert first["reason"] == "The quote is not in the answer."


def test_a_forbidden_claim_the_answer_makes_fails_the_case() -> None:
    answer = "Support is 24x7 on every plan."
    ask = _replies(
        {
            "16x5": {"verdict": "not_stated", "quote": ""},
            "24x7": {"verdict": "stated", "quote": "Support is 24x7 on every plan."},
        }
    )
    result = judge_answer(answer, MUST, MUST_NOT, ask, model_id="m1")
    assert result["passed"] is False
    assert result["detail"] == "0 of 1 facts stated, 1 forbidden claims made"


def test_the_judge_is_held_to_the_statement_and_the_agents_instructions() -> None:
    seen: list[tuple[str, str]] = []

    def ask(task: str, evidence: str) -> str | None:
        seen.append((task, evidence))
        return '{"verdict":"stated","quote":"Premium cloud lists 16x5 support."}'

    result = judge_answer(
        ANSWER,
        MUST,
        [],
        ask,
        model_id="m1",
        instructions="Answer from the pages. Do not ask the visitor a question.",
    )
    assert result["passed"] is True
    task, evidence = seen[0]
    assert "paraphrase" in task
    assert "clarifying question" in task
    assert "Do not ask the visitor a question." in evidence
    assert "agent_instructions" in evidence


def test_a_reply_that_is_not_the_schema_is_failed_not_guessed() -> None:
    def ask(task: str, evidence: str) -> str | None:
        del task, evidence
        return "Yes, it says that."

    result = judge_answer(ANSWER, MUST, [], ask, model_id="m1")
    assert result["passed"] is False
    assert result["verdict"] == "failed"
    assert result["items"][0]["verdict"] == "failed"  # type: ignore[index]


def test_no_judge_model_fails_every_statement() -> None:
    result = judge_answer(ANSWER, MUST, MUST_NOT, None, model_id="")
    assert result["passed"] is False
    items = result["items"]
    assert isinstance(items, list)
    assert {item["verdict"] for item in items} == {"failed"}


def test_the_assertion_needs_a_statement_and_old_rubric_files_keep_their_meaning() -> None:
    parsed = parse_assertion(
        {"type": "llm_judge", "must": ["a"], "mustNot": ["b"], "judgeAlias": "judge"}
    )
    assert parsed == {"type": "llm_judge", "must": ["a"], "must_not": ["b"], "judge_alias": "judge"}
    assert parse_assertion({"type": "llm_judge", "rubric": "x"})["type"] == "lexical_overlap"
    with pytest.raises(ValidationFailedError):
        parse_assertion({"type": "llm_judge"})


# The stand-in answers the agent's turn with ANSWER and each judge question by the
# statement it names. Judge questions carry the documents system prompt.
_JUDGE_SYSTEM = "You answer only from the untrusted documents"


def _scripts(answer: str) -> list[dict[str, object]]:
    stated = '{"verdict":"stated","quote":"Premium cloud lists 16x5 support."}'
    return [
        {
            "match": {"system_contains": _JUDGE_SYSTEM, "regex": "Statement: [^\\n]*16x5"},
            "respond": {"text": stated},
        },
        {
            "match": {"system_contains": _JUDGE_SYSTEM, "regex": "Statement: [^\\n]*24x7"},
            "respond": {"text": '{"verdict":"not_stated","quote":""}'},
        },
        {"match": {}, "respond": {"text": answer}},
    ]


def _actor() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
        display_name="Admin",
    )


def _run(store: ChatService) -> dict[str, object]:
    actor = _actor()
    life = AgentLifecycle(store)
    created = life.create(actor, slug="judged", name="Judged", description="judged")
    agent_id = uuid.UUID(str(created["id"]))
    life.publish(actor, agent_id, change_note="first")
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Site", "kind": "functional", "agent_id": agent_id})
    lines = [
        orjson.dumps(
            {
                "name": f"support hours {index}",
                "tags": ["single"],
                "input": {"messages": ["what support hours does the premium cloud have"]},
                "assertions": [{"type": "llm_judge", "must": MUST, "mustNot": MUST_NOT}],
            }
        ).decode()
        for index in range(3)
    ]
    report = book.import_text(actor, suite["id"], "\n".join(lines))  # type: ignore[arg-type]
    assert report == {"imported": 3, "errors": []}
    run = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    assert run["status"] == "completed"
    results = book.results(actor, run["id"])  # type: ignore[arg-type]
    assert [row["case"]["name"] for row in results] == [  # type: ignore[index]
        f"support hours {index}" for index in range(3)
    ]
    return {"summary": run["summary"], "results": results}


def test_an_eval_run_judges_each_case_with_the_model(stand_in: StandIn) -> None:
    store = demo_store(allow_loopback=True)
    stand_in.script("judge-pass", _scripts(ANSWER))
    stand_in.connect(store, demo_id("tenant"), script_set="judge-pass")
    ran = _run(store)
    summary = ran["summary"]
    assert isinstance(summary, dict)
    results = ran["results"]
    assert isinstance(results, list)
    first = results[0]
    assert summary["pass_rate"] == 1, (first["output_text"], first["scores"])
    scores = first["scores"]
    judged = scores["llm_judge_0"]
    assert judged["verdict"] == "judged"
    assert judged["detail"] == "1 of 1 facts stated, 0 forbidden claims made"


def test_an_answer_without_the_fact_fails_the_run(stand_in: StandIn) -> None:
    store = demo_store(allow_loopback=True)
    stand_in.script("judge-fail", _scripts("Support hours depend on your plan."))
    stand_in.connect(store, demo_id("tenant"), script_set="judge-fail")
    summary = _run(store)["summary"]
    assert isinstance(summary, dict)
    assert summary["pass_rate"] == 0


def test_a_case_that_cannot_run_is_a_failed_case_and_the_run_still_finishes(
    stand_in: StandIn, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ar_domain.evals import runner

    store = demo_store(allow_loopback=True)
    stand_in.script("judge-broken", _scripts(ANSWER))
    stand_in.connect(store, demo_id("tenant"), script_set="judge-broken")
    real = runner._run_case
    calls = {"n": 0}

    async def flaky(store_: object, row: object, case: dict[str, object]) -> dict[str, object]:
        calls["n"] += 1
        if case.get("name") == "support hours 1":
            raise RuntimeError("store went away")
        return await real(store_, row, case)  # type: ignore[arg-type]

    monkeypatch.setattr(runner, "_run_case", flaky)
    ran = _run(store)
    summary = ran["summary"]
    assert isinstance(summary, dict)
    assert summary["cases"] == 3
    assert summary["passed"] == 2
    results = ran["results"]
    assert isinstance(results, list)
    broken = next(row for row in results if row["case"]["name"] == "support hours 1")
    assert broken["scores"]["case_error"]["detail"].startswith("The case did not run: RuntimeError")


def test_scoring_a_case_twice_keeps_one_result(stand_in: StandIn) -> None:
    import asyncio

    from ar_domain.evals.runner import begin_eval_run, finish_eval_run, score_eval_case

    store = demo_store(allow_loopback=True)
    stand_in.script("judge-twice", _scripts(ANSWER))
    stand_in.connect(store, demo_id("tenant"), script_set="judge-twice")
    actor = _actor()
    life = AgentLifecycle(store)
    created = life.create(actor, slug="twice", name="Twice", description="twice")
    agent_id = uuid.UUID(str(created["id"]))
    life.publish(actor, agent_id, change_note="first")
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Twice", "kind": "functional", "agent_id": agent_id})
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "hours",
            "input": {"messages": ["support hours?"]},
            "assertions": [{"type": "llm_judge", "must": MUST, "mustNot": MUST_NOT}],
        },
    )
    store.defer_eval_runs = True
    queued = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    run_id = uuid.UUID(str(queued["id"]))
    case_ids = begin_eval_run(store, run_id)
    assert len(case_ids) == 1
    first = asyncio.run(score_eval_case(store, run_id, case_ids[0]))
    again = asyncio.run(score_eval_case(store, run_id, case_ids[0]))
    assert first is True
    assert again is True
    assert len([r for r in store.eval_results.values() if r["eval_run_id"] == run_id]) == 1
    assert finish_eval_run(store, run_id)["pass_rate"] == 1


def test_a_case_that_breaks_ends_the_agent_runs_it_left_working(
    stand_in: StandIn, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ar_domain.conversations.logic import run_is_active
    from ar_domain.evals import runner

    store = demo_store(allow_loopback=True)
    stand_in.script("judge-leftover", _scripts(ANSWER))
    stand_in.connect(store, demo_id("tenant"), script_set="judge-leftover")
    real = runner._run_case

    async def breaks_after_starting(
        store_: object, row: dict[str, object], case: dict[str, object]
    ) -> dict[str, object]:
        if case.get("name") != "support hours 1":
            return await real(store_, row, case)  # type: ignore[arg-type]
        # The agent run the case started, still working when the case breaks.
        run_id = uuid.uuid4()
        store.runs[run_id] = {
            "id": run_id,
            "tenant_id": demo_id("tenant"),
            "trigger": "eval",
            "status": "running",
            "eval_context": {"eval_run_id": str(row["id"]), "case_id": str(case["id"])},
        }
        raise RuntimeError("the store went away mid-case")

    monkeypatch.setattr(runner, "_run_case", breaks_after_starting)
    _run(store)
    left = [
        run
        for run in store.runs.values()
        if run.get("trigger") == "eval" and run_is_active(str(run.get("status")))
    ]
    assert left == []
    ended = [
        run
        for run in store.runs.values()
        if (run.get("error") or {}).get("code") == "eval_case_ended"
    ]
    assert len(ended) == 1


def test_a_refused_run_writes_no_message() -> None:
    from types import SimpleNamespace

    from ar_common.errors import PlanLimitReachedError

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    created = AgentLifecycle(store).create(
        _actor(), slug="limited", name="Limited", description="x"
    )
    agent_id = uuid.UUID(str(created["id"]))
    AgentLifecycle(store).publish(_actor(), agent_id, change_note="first")
    conversation = store.create_conversation(tenant, user, agent_id)
    before = len(store.messages)
    from ar_domain.identity import plan_limits

    original = plan_limits.load_limits
    plan_limits.load_limits = lambda _store, _tenant: SimpleNamespace(max_concurrent_runs=0)  # type: ignore[assignment]
    try:
        with pytest.raises(PlanLimitReachedError):
            store.post_message(
                tenant, user, uuid.UUID(str(conversation["id"])), "hello", schedule=False
            )
    finally:
        plan_limits.load_limits = original  # type: ignore[assignment]
    assert len(store.messages) == before


def test_cancelling_a_run_cancels_its_workflow() -> None:
    cancelled: list[str] = []

    class _Handle:
        def __init__(self, workflow_id: str) -> None:
            self.workflow_id = workflow_id

        async def cancel(self) -> None:
            cancelled.append(self.workflow_id)

    class _Client:
        def get_workflow_handle(self, workflow_id: str) -> _Handle:
            return _Handle(workflow_id)

    store = demo_store()
    actor = _actor()
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Cancel", "kind": "functional"})
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "x",
            "input": {"messages": ["hello"]},
            "assertions": [{"type": "contains", "value": "hello"}],
        },
    )
    store.defer_eval_runs = True  # type: ignore[attr-defined]
    queued = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    store.temporal_client = _Client()  # type: ignore[attr-defined]
    view = book.cancel(actor, uuid.UUID(str(queued["id"])))
    assert view["status"] == "cancelled"
    assert cancelled == [f"eval-{queued['id']}"]


def test_a_conversation_is_judged_on_every_answer_not_only_the_last() -> None:
    transcript = [
        {"user": "is it hosted?", "assistant": "Both cloud and on-premises are offered."},
        {"user": "support hours on premium?", "assistant": "Premium cloud lists 16x5 support."},
        {"user": "how do I see a demo?", "assistant": "Use the Request a Demo form."},
    ]
    asked: list[str] = []

    def ask(task: str, evidence: str) -> str | None:
        asked.append(evidence)
        if "16x5" in task:
            return '{"verdict":"stated","quote":"Premium cloud lists 16x5 support."}'
        if "on-premises" in task:
            return '{"verdict":"stated","quote":"Both cloud and on-premises are offered."}'
        return '{"verdict":"not_stated","quote":""}'

    result = judge_answer(
        "Use the Request a Demo form.",
        ["Both cloud and on-premises deployment are offered.", "Premium lists 16x5 support."],
        ["Says 24x7 support."],
        ask,
        model_id="m1",
        transcript=transcript,
    )
    assert result["passed"] is True
    assert "Turn 2, the assistant answered" in asked[0]
    single = judge_answer(
        "Use the Request a Demo form.",
        ["Premium lists 16x5 support."],
        [],
        ask,
        model_id="m1",
        transcript=transcript[-1:],
    )
    # One turn: only that answer is the evidence, and its words hold no such quote.
    assert single["passed"] is False
