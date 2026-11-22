"""A research question is split into sentences, and a search that fails does not hang the run."""

from ar_domain.research.driver import store_results
from ar_domain.research.engine import (
    _subtask_failure,
    initial_state,
    pending_subtasks,
    plan_queries,
    state_of,
)


def test_a_full_stop_inside_a_word_does_not_split_the_question() -> None:
    question = "What does Mozilla Public License 2.0 require when distributing executable form?"
    assert [row["text"] for row in plan_queries(question, breadth=4)] == [
        "What does Mozilla Public License 2.0 require when distributing executable form"
    ]
    assert [row["text"] for row in plan_queries("See example.com. Is it up? Yes!", breadth=4)] == [
        "See example.com",
        "Is it up",
        "Yes",
    ]
    assert plan_queries("  ", breadth=4) == []
    assert [row["text"] for row in plan_queries("?!", breadth=4)] == ["?!"]


def test_a_search_that_keeps_failing_is_dropped_and_its_reason_kept() -> None:
    state = initial_state("kites")
    state["queries"] = [
        {"id": "1", "text": "kites", "status": "pending"},
        {"id": "2", "text": "string", "status": "pending"},
    ]
    run: dict[str, object] = {"checkpoint": {"research": state}}
    store_results(run, {"1": {"status": "failed", "reason": "the provider refused"}, "2": "junk"})
    assert [row["id"] for row in pending_subtasks(state_of(run, "kites"))] == ["1", "2"]
    store_results(
        run,
        {"1": {"status": "failed", "reason": "the provider refused"}, "2": {"status": "done"}},
    )
    after = state_of(run, "kites")
    assert pending_subtasks(after) == []
    assert _subtask_failure(after) == "the provider refused"


def test_a_search_that_succeeds_on_the_second_go_is_not_a_failure() -> None:
    state = initial_state("kites")
    state["queries"] = [{"id": "1", "text": "kites", "status": "pending"}]
    run: dict[str, object] = {"checkpoint": {"research": state}}
    store_results(run, {"1": {"status": "failed"}})
    store_results(run, {"1": {"status": "done", "sources": []}})
    after = state_of(run, "kites")
    assert pending_subtasks(after) == []
    assert _subtask_failure(after) == ""
    assert _subtask_failure({}) == ""
