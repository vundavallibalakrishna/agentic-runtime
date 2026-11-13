"""Public JSON keys are camelCase. Python names and stored documents stay snake_case."""

from datetime import UTC, datetime

from ar_common.json_api import camelize
from ar_contracts.budget import RunBudget
from ar_contracts.identity import Me
from ar_contracts.json_api import Page, ProblemDetails, page_body, public_dump


def test_wire_format_round_trip() -> None:
    budget = RunBudget(
        max_steps=1,
        max_tokens=2,
        max_cost_micros=3,
        max_wall_clock_s=4,
        max_tool_calls=5,
        max_parallel_tool_calls=6,
    )
    dumped = public_dump(budget)
    assert "maxSteps" in dumped
    assert "max_steps" not in dumped
    assert dumped == public_dump(RunBudget.model_validate(dumped))
    stored = budget.model_dump(by_alias=False)
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
    body = problem.model_dump()
    assert body["requestId"] == "req_1"
    assert body["code"] == "not_found"
    page = page_body([{"display_name": "Ada"}], next_cursor=None)
    assert page["items"] == [{"displayName": "Ada"}]
    assert page["nextCursor"] is None
    assert page["hasMore"] is False
    assert Page.model_validate(page).has_more is False


def test_request_options_are_not_camelized() -> None:
    body = {
        "request_options": {"chat_template_kwargs": {"enable_thinking": False}},
        "created_at": "2026-11-05",
    }
    public = camelize(body)
    assert public == {
        "requestOptions": {"chat_template_kwargs": {"enable_thinking": False}},
        "createdAt": "2026-11-05",
    }
    assert camelize(public) == public


def test_tool_input_schema_parameter_names_are_not_camelized() -> None:
    # A tool's input_schema is a JSON Schema whose properties keys are parameter names the
    # tool accepts (snake_case, e.g. file_id). The field name becomes camelCase, but the
    # schema's keys must survive so the Tools screen shows names that work.
    body = {
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "max_rows": {"type": "integer"}},
            "required": ["file_id"],
        },
        "output_schema": {"properties": {"row_count": {"type": "integer"}}},
        "risk_class": "R0",
    }
    public = camelize(body)
    assert public["inputSchema"]["properties"] == {
        "file_id": {"type": "string"},
        "max_rows": {"type": "integer"},
    }
    assert public["inputSchema"]["required"] == ["file_id"]
    assert public["outputSchema"]["properties"] == {"row_count": {"type": "integer"}}
    assert public["riskClass"] == "R0"


def test_identity_me_accepts_alias_and_python_name() -> None:
    stamp = datetime(2026, 10, 20, tzinfo=UTC)
    by_python = Me.model_validate(
        {"id": "user-1", "display_name": "Ada", "created_at": stamp, "roles": ["tenant_admin"]}
    )
    by_alias = Me.model_validate(
        {"id": "user-1", "displayName": "Ada", "createdAt": stamp, "roles": ["tenant_admin"]}
    )
    assert by_python.display_name == by_alias.display_name == "Ada"
    assert by_python.created_at == by_alias.created_at == stamp
    dumped = by_python.model_dump(mode="json")
    assert dumped["displayName"] == "Ada"
    assert dumped["createdAt"].startswith("2026-10-20")
    assert dumped["roles"] == ["tenant_admin"]
    assert "display_name" not in dumped
    assert "created_at" not in dumped
