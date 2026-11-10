"""Stage 13: charts keep their rows, public replies hide thinking, follow-ups parse."""

from ar_domain.exposure.public import event_order_ok, public_content, public_events
from ar_domain.loop.followups import parse_followups
from ar_domain.models.logic import completion_message
from ar_domain.tools.charts import dispatch_chart
from ar_domain.tools.structured import check_response_format, schema_for
from ar_testing.demo import demo_store


def test_chart_presentation_keeps_the_rows_the_png_used() -> None:
    store = demo_store()
    result = dispatch_chart(
        store,
        "chart",
        {
            "kind": "bar",
            "title": "Counts",
            "rows": [{"label": "North", "value": 2}, {"label": "South", "value": 5}],
        },
    )
    assert result is not None and result["is_error"] is False
    presentation = result["structured"]["presentation"]
    assert presentation["kind"] == "chart"
    assert presentation["rows"] == [
        {"label": "North", "value": 2.0},
        {"label": "South", "value": 5.0},
    ]
    assert presentation["files"]


def test_public_reply_returns_parts_and_hides_thinking() -> None:
    message = {
        "text": "The notes are complete.",
        "content": [
            {"type": "text", "text": "The notes are complete."},
            {"type": "reasoning", "text": "private"},
            {"type": "followups", "prompts": ["What is missing?"]},
        ],
    }
    parts = public_content(message)
    assert [part["type"] for part in parts] == ["text", "followups"]
    events = public_events(
        [{"type": "reasoning.delta"}, {"type": "message.delta"}, {"type": "run.completed"}],
        show_reasoning=False,
    )
    assert [event["type"] for event in events] == ["message.delta", "run.completed"]
    shown = public_events(
        [{"type": "reasoning.delta"}, {"type": "message.completed"}], show_reasoning=True
    )
    assert shown[0]["type"] == "reasoning.delta"


def test_event_order_requires_a_start_before_a_close() -> None:
    assert event_order_ok(
        [
            "run.started",
            "plan.updated",
            "message.started",
            "reasoning.delta",
            "tool_call.started",
            "tool_call.completed",
            "message.delta",
            "message.completed",
            "run.completed",
        ]
    )
    assert not event_order_ok(["message.completed", "message.started"])
    assert not event_order_ok(["run.completed", "message.delta"])


def test_followups_parse_a_json_array_and_ignore_prose() -> None:
    assert parse_followups('["What changed?", "Show the chart"]', limit=3) == [
        "What changed?",
        "Show the chart",
    ]
    assert parse_followups("I am not sure.", limit=3) == []


def test_response_format_overrides_the_agent_schema() -> None:
    definition = {"output": {"jsonSchema": {"type": "object"}}}
    override = {"type": "object", "properties": {"answer": {"type": "string"}}}
    assert schema_for(definition, override) == override
    assert schema_for(definition, None) == {"type": "object"}
    checked = check_response_format({"type": "object"})
    assert checked == {"type": "object"}


def test_completion_keeps_a_think_trace_off_the_answer() -> None:
    parsed = completion_message(
        {
            "choices": [
                {
                    "message": {
                        "content": "<think>weigh the notes</think>The file is complete.",
                        "reasoning_content": "second pass",
                    }
                }
            ]
        }
    )
    assert parsed["text"] == "The file is complete."
    assert "weigh the notes" in str(parsed["reasoning"])
    assert "second pass" in str(parsed["reasoning"])
