"""An agent's answer-length limit is the last thing the model reads before it answers."""

import pytest
from pydantic import ValidationError

from ar_contracts.definitions import OutputSpec
from ar_domain.tools.agent_loop import _configured_max_tokens
from ar_domain.workspace.turn import _append_system, length_rule, max_words


def _hits() -> dict[str, object]:
    return {
        "hits": [
            {"title": "Industries", "text": "Banks and insurers use the platform.", "anchor": ""},
            {"title": "Pricing", "text": "Pricing is on request.", "anchor": ""},
        ],
        "trace": {},
    }


def test_the_limit_is_a_setting_with_bounds() -> None:
    assert OutputSpec().max_words is None
    assert OutputSpec.model_validate({"maxWords": 120}).max_words == 120
    for wrong in (0, 5, 6000):
        with pytest.raises(ValidationError):
            OutputSpec.model_validate({"maxWords": wrong})


def test_the_rule_comes_after_the_passages() -> None:
    definition = {
        "instructions": "You answer questions about the company.",
        "output": {"maxWords": 120},
    }
    run: dict[str, object] = {}

    _append_system(run, definition, None, _hits())

    system = str(run["prompt_messages"][0]["content"])  # type: ignore[index]
    assert system.rstrip().endswith(length_rule(definition))
    assert "at most 120 words" in system
    assert system.index("Pricing is on request.") < system.index("at most 120 words")


def test_no_limit_adds_nothing() -> None:
    definition = {"instructions": "Help."}
    run: dict[str, object] = {}
    _append_system(run, definition, None, _hits())
    assert "Length:" not in str(run["prompt_messages"][0]["content"])  # type: ignore[index]
    assert length_rule(definition) == ""
    assert max_words({"output": {"maxWords": True}}) is None


def test_the_ceiling_stops_a_runaway_answer_but_not_a_kept_one() -> None:
    # Four tokens a word: far above what a 120-word answer with citations needs.
    assert _configured_max_tokens({"output": {"max_words": 120}}) == 480
    assert _configured_max_tokens({"output": {"maxWords": 20}}) == 256
    # An agent that sets its own output limit keeps it.
    assert (
        _configured_max_tokens(
            {"output": {"maxWords": 120}, "model": {"params": {"maxOutputTokens": 900}}}
        )
        == 900
    )
    assert _configured_max_tokens({"instructions": "Help."}) is None
