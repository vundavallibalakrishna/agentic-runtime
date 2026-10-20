"""Public JSON keys are camelCase. Python names stay snake_case."""

from ar_contracts.budget import RunBudget
from ar_contracts.json_api import Page, ProblemDetails, contract_violations, page_body


def test_public_models_have_camel_case_aliases() -> None:
    assert contract_violations() == []


def test_wire_format_round_trip() -> None:
    budget = RunBudget(
        max_steps=1,
        max_tokens=2,
        max_cost_micros=3,
        max_wall_clock_s=4,
        max_tool_calls=5,
        max_parallel_tool_calls=6,
    )
    dumped = budget.public_dump()
    assert "maxSteps" in dumped
    assert "max_steps" not in dumped
    assert dumped == RunBudget.model_validate(dumped).public_dump()
    stored = budget.model_dump()
    assert stored["max_steps"] == 1
    assert "maxSteps" not in stored


def test_problem_and_page_envelopes() -> None:
    problem = ProblemDetails(
        type="https://docs.agentic-runtime.dev/errors/not_found",
        title="Not found",
        status=404,
        code="not_found",
        detail="gone",
        instance="/api/v1/me",
        request_id="req_1",
    )
    body = problem.public_dump()
    assert body["requestId"] == "req_1"
    assert body["code"] == "not_found"
    page = page_body([{"display_name": "Ada"}], next_cursor=None)
    assert page["items"] == [{"displayName": "Ada"}]
    assert page["nextCursor"] is None
    assert page["hasMore"] is False
    assert Page.model_validate(page).has_more is False
