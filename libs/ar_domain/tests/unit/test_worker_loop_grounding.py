"""What a turn found in its first step is still there when a later step ends it."""

from ar_domain.tools.agent_loop import _with_trace
from ar_domain.tools.worker_loop import read_worker_loop, write_worker_loop

_PASSAGE = {
    "document_id": "d1",
    "title": "Business continuity",
    "snippet": "Prepare for outages.",
    "anchor": "p1",
    "uri": "https://example.test/continuity/",
}


def _saved_and_loaded(run: dict[str, object]) -> dict[str, object]:
    """The run as the next activity gets it: only its saved columns."""
    return {"id": run["id"], "checkpoint": run["checkpoint"]}


def test_a_turn_that_called_a_tool_still_cites_the_passages_in_its_prompt() -> None:
    run: dict[str, object] = {
        "id": "r1",
        "retrieval": {"hits": [_PASSAGE]},
        "loaded_skill": {"slug": "s"},
        "tools_used": ["knowledge.search"],
    }
    write_worker_loop(run, {"opened": True, "phase": "tools", "messages": []})

    later = _saved_and_loaded(run)
    state = read_worker_loop(later)

    assert state is not None
    assert later["loaded_skill"] == {"slug": "s"}
    parts = _with_trace(object(), "Prepare for outages [1].", later)
    cited = [part for part in parts if part["type"] == "citation_ref"]
    assert [part["citation"]["uri"] for part in cited] == ["https://example.test/continuity/"]
    assert {"type": "reading", "tools": ["knowledge.search"]} in parts


def test_a_later_step_adds_to_what_was_carried_and_does_not_replace_it() -> None:
    run: dict[str, object] = {"id": "r1", "tools_used": ["web.search"]}
    write_worker_loop(run, {"opened": True, "messages": []})
    later = _saved_and_loaded(run)
    read_worker_loop(later)
    later["tools_used"] = [*later["tools_used"], "knowledge.search"]  # type: ignore[misc]
    write_worker_loop(later, {"opened": True, "messages": []})

    last = _saved_and_loaded(later)
    read_worker_loop(last)

    assert last["tools_used"] == ["web.search", "knowledge.search"]


def test_a_turn_that_found_nothing_saves_nothing_extra() -> None:
    run: dict[str, object] = {"id": "r1"}
    write_worker_loop(run, {"opened": True, "messages": []})

    assert "grounding" not in run["checkpoint"]["worker_loop"]  # type: ignore[index]
