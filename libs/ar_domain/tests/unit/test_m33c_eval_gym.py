"""M33c tool-choice gym: dry-run scorecard and the gates that catch a silent model."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from ar_domain.chat.service import ChatService
from ar_domain.evals.gym.cli import main
from ar_domain.evals.gym.live import LIVE_KEY, LiveConfigError, install_live, live_requested
from ar_domain.evals.gym.policy import choose
from ar_domain.evals.gym.runner import run_suite
from ar_domain.evals.gym.score import ObservedCall, Report, render_scorecard, score_observation
from ar_domain.evals.gym.tasks import ArgRule, Expectation, Task, load_tasks, tasks_path
from ar_testing.demo import connect_embeddings, demo_store
from ar_testing.demo_tenant import seed_demo_tenant
from ar_testing.objects import MemoryObjectStore


def _make_store() -> ChatService:
    """The seeded tenant the gym runs on, built by test tooling (M38b-T04d)."""
    store = ChatService()
    seed_demo_tenant(store)
    return store


_REQUIRED = (
    "general.code",
    "general.shell",
    "general.read_file",
    "general.fetch",
    "general.http",
    "data.query",
    "general.chart",
    "general.export_table",
    "knowledge.search",
    "documents.summarise",
    "documents.check",
)


def _prepare(store: Any) -> None:
    """The gym's world gets the stand-ins a test may use: models and an object store."""
    connect_embeddings(store)
    store.objects = MemoryObjectStore()


def test_tasks_cover_the_tool_choice_set() -> None:
    tasks = load_tasks()
    tools = {task.expect.tool for task in tasks}
    assert set(_REQUIRED) <= tools
    assert any(task.expect.grounded == "not_found" for task in tasks)
    assert any(task.expect.terminal == "waiting_approval" for task in tasks)


def test_scripted_model_picks_python_without_reading_the_scorecard() -> None:
    call = choose("Use Python to print 17 * 19. Reply with only the number.")
    assert call is not None
    assert call["name"] == "general__code"
    arguments = call["arguments"]
    assert isinstance(arguments, dict)
    assert "17" in str(arguments["source"])


def _chain_task() -> Task:
    return Task(
        id="acc-copy-token",
        title="Read then write",
        instruction="Read note.txt and write the token into copy.txt.",
        attachments=(),
        expect=Expectation(
            tool="general.read_file",
            args=(),
            contains=("copy.txt",),
            must_not_contain=(),
            grounded="quote",
            terminal="completed",
            chain=("general.read_file", "general.write_file"),
        ),
    )


def _chain_calls(names: list[str]) -> list[ObservedCall]:
    return [
        ObservedCall(name=name, arguments={}, result_text="FILE-19 copy.txt", status="succeeded")
        for name in names
    ]


def test_a_chain_passes_when_the_tools_run_in_order() -> None:
    score = score_observation(
        _chain_task(),
        calls=_chain_calls(["general.read_file", "general.write_file"]),
        answer="wrote copy.txt",
        status="completed",
    )
    assert score.tool_selected is True
    assert score.expected_tool == "general.read_file → general.write_file"


def test_a_chain_fails_when_a_tool_is_missing_or_out_of_order() -> None:
    missing = score_observation(
        _chain_task(),
        calls=_chain_calls(["general.read_file"]),
        answer="wrote copy.txt",
        status="completed",
    )
    assert missing.tool_selected is False
    reversed_order = score_observation(
        _chain_task(),
        calls=_chain_calls(["general.write_file", "general.read_file"]),
        answer="wrote copy.txt",
        status="completed",
    )
    assert reversed_order.tool_selected is False


def test_zero_tool_calls_fail_even_when_the_number_looks_right() -> None:
    score = score_observation(
        _quote_task(),
        calls=[],
        answer="323",
        status="completed",
    )
    assert score.tool_selected is False
    assert score.passed is False


def test_invented_answer_is_not_grounded() -> None:
    score = score_observation(
        _quote_task(),
        calls=[
            ObservedCall(
                name="general.code",
                arguments={"source": "print(17 * 19)"},
                result_text="exit 0\n323",
                status="succeeded",
            )
        ],
        answer="The answer is 999",
        status="completed",
    )
    assert score.tool_selected is True
    assert score.args_ok is True
    assert score.answer_grounded is False


def test_not_found_fails_when_the_answer_invents_the_menu() -> None:
    task = _not_found_task()
    score = score_observation(
        task,
        calls=[
            ObservedCall(
                name="documents.check",
                arguments={"requirements": ["cafeteria"]},
                result_text="The cafeteria serves mars stew on Tuesdays: not_found",
                status="succeeded",
            )
        ],
        answer="not_found, but mars stew is served on Tuesdays",
        status="completed",
    )
    assert score.answer_grounded is False


def test_not_found_passes_when_the_tool_and_the_answer_agree() -> None:
    score = score_observation(
        _not_found_task(),
        calls=[
            ObservedCall(
                name="documents__check",
                arguments={"documentId": "doc", "requirements": ["cafeteria"]},
                result_text="requirement: not_found",
                status="succeeded",
            )
        ],
        answer="not_found. The passage was not found.",
        status="completed",
    )
    assert score.passed is True


def test_approval_fails_when_the_answer_claims_http_200() -> None:
    score = score_observation(
        _approval_task(),
        calls=[
            ObservedCall(
                name="general.http",
                arguments={"method": "POST", "url": "https://example.com/gym/orders"},
                result_text="Waiting for approval.",
                status="awaiting_approval",
            )
        ],
        answer="HTTP 200 created the order",
        status="waiting_approval",
    )
    assert score.tool_selected is True
    assert score.args_ok is True
    assert score.answer_grounded is False


def test_live_flag_is_off_unless_the_env_flag_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_EVAL_GYM_LIVE", raising=False)
    monkeypatch.setenv(LIVE_KEY, "secret-value")
    assert live_requested() is False
    assert main(["--live"]) == 2


def test_live_flag_without_a_key_does_not_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_EVAL_GYM_LIVE", "1")
    monkeypatch.delenv(LIVE_KEY, raising=False)
    with pytest.raises(LiveConfigError):
        run_suite(live=True)
    assert main([]) == 2


def test_dry_run_does_not_store_the_cert_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_KEY, "secret-value")
    store = demo_store()
    assert "secret-value" not in str(store.providers)


def test_live_install_keeps_the_key_on_the_provider_row() -> None:
    store = demo_store()
    install_live(store, uuid.uuid4(), key="secret-value")
    assert any(row.get("api_key") == "secret-value" for row in store.providers.values())
    assert "secret-value" not in render_scorecard(Report(mode="dry-run", scores=()))


def test_dry_run_gym_passes_and_matches_the_committed_scorecard() -> None:
    report = run_suite(make_store=_make_store, live=False, prepare=_prepare)
    assert report.mode == "dry-run"
    assert report.proof == "unit"
    assert report.percent == 100
    assert report.passed_count == report.total
    committed = tasks_path().parents[1] / "m33c-scorecard.md"
    assert committed.read_text(encoding="utf-8") == render_scorecard(report)


def _quote_task() -> Task:
    return Task(
        id="general-code",
        title="Python arithmetic",
        instruction="Use Python to print 17 * 19.",
        attachments=(),
        expect=Expectation(
            tool="general.code",
            args=(ArgRule("source", contains=("17", "19")),),
            contains=("323",),
            must_not_contain=(),
            grounded="quote",
            terminal="completed",
        ),
    )


def _not_found_task() -> Task:
    return Task(
        id="refuse-not-found",
        title="Say not_found",
        instruction="Check the requirement.",
        attachments=(),
        expect=Expectation(
            tool="documents.check",
            args=(ArgRule("requirements", contains=("cafeteria",)),),
            contains=(),
            must_not_contain=("mars stew is served", "555-0100"),
            grounded="not_found",
            terminal="completed",
        ),
    )


def _approval_task() -> Task:
    return Task(
        id="http-post-approval",
        title="HTTP POST",
        instruction="Send a POST.",
        attachments=(),
        expect=Expectation(
            tool="general.http",
            args=(
                ArgRule("method", equals="POST"),
                ArgRule("url", contains=("example.com/gym/orders",)),
            ),
            contains=(),
            must_not_contain=("HTTP 200", "created the order"),
            grounded="approval",
            terminal="waiting_approval",
        ),
    )
