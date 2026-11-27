"""A step is labelled with the alias and the model that answered it."""

import uuid

from ar_domain.tools.agent_loop import _note_endpoint


def test_the_step_records_the_model_that_ran() -> None:
    events: list[tuple[str, dict[str, object]]] = []

    class _Store:
        def __init__(self) -> None:
            self.messages: dict[object, object] = {}

        def _emit(self, run: dict[str, object], kind: str, data: dict[str, object]) -> None:
            del run
            events.append((kind, data))

    run: dict[str, object] = {"id": uuid.uuid4()}
    _note_endpoint(
        _Store(),
        run,
        {
            "answered_model": "claude-haiku",
            "model_alias": "fast",
            "resolved_model_id": "claude-haiku",
        },
        2,
    )
    assert events[0][0] == "model.called"
    assert events[0][1]["model_alias"] == "fast"
    assert events[0][1]["model"] == "claude-haiku"
    trace = run["model_trace"]
    assert isinstance(trace, list)
    assert trace[0]["model"] == "claude-haiku"
    assert trace[0]["model_alias"] == "fast"
