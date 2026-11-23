"""A routine's run is started with the turn payload worked out where the run was opened."""

from ar_system.workflows.routine_run import _turn_payload


def test_the_carried_allowance_reaches_the_turn() -> None:
    carried = {"run_id": "r1", "text": "Run now", "max_steps": 48, "step_timeout_s": 300}
    started = _turn_payload({"run_id": "r1", "text": "ignored", "workflow": carried})
    assert started["max_steps"] == 48
    assert started["step_timeout_s"] == 300
    assert started["text"] == "Run now"
    assert (started["names"], started["steps"]) == ([], True)


def test_a_run_prepared_by_an_older_release_still_starts() -> None:
    started = _turn_payload({"run_id": "r1", "text": "Run now"})
    assert started == {"run_id": "r1", "text": "Run now", "names": [], "steps": True}
