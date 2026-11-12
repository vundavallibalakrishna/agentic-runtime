"""Stage 10 loop quality: plan, repair, routing, context. Proof: unit."""

import time
import uuid

from ar_domain.evals.harness import regressed
from ar_domain.loop.context import fit_messages, read_output, retain_output
from ar_domain.loop.planning import parse_plan, planning_enabled
from ar_domain.loop.repair import apply_tool_failure, output_repair_limit, tool_failure_limit
from ar_domain.loop.routing import (
    CircuitBreaker,
    MemoryCircuitClient,
    circuit_key,
    retryable_status,
)


def test_eval_gate_flags_a_lower_pass_rate() -> None:
    assert regressed(
        {"pass_rate": 0.9, "tool_call_correctness": 1, "citation_validity": 1, "refusal_rate": 1},
        {"pass_rate": 1, "tool_call_correctness": 1, "citation_validity": 1, "refusal_rate": 1},
    ) == ["pass_rate"]


def test_plan_parses_and_is_optional() -> None:
    assert planning_enabled({"planning": {"enabled": True}}) is True
    assert planning_enabled({}) is False
    items, error = parse_plan('{"steps":[{"id":"1","title":"Read the note"}]}')
    assert error == ""
    assert items is not None and items[0]["title"] == "Read the note"
    missing, problem = parse_plan("not json")
    assert missing is None
    assert "JSON" in problem


def test_repair_budget_and_structured_notice() -> None:
    assert output_repair_limit({}) == 1
    assert tool_failure_limit({"repair": {"max_attempts": 2}}) == 2
    assistant: dict[str, object] = {}
    notice = apply_tool_failure(assistant, failed_open=True)
    assert notice is not None
    assert assistant["tool_failure"] == notice
    assert apply_tool_failure(assistant, failed_open=False) is None


def test_circuit_opens_and_allows_a_later_trial() -> None:
    client = MemoryCircuitClient()
    breaker = CircuitBreaker(client)
    key = circuit_key(uuid.uuid4(), "primary")
    assert breaker.allow(key) is True
    breaker.failure(key)
    breaker.failure(key)
    assert breaker.allow(key) is True
    breaker.failure(key)
    assert breaker.allow(key) is False
    assert retryable_status(429) is True
    assert retryable_status(200) is False
    opened = time.time() - 31
    client.set(key, '{"state":"open","failures":3,"opened_at":%s}' % opened)
    assert breaker.allow(key, now=time.time()) is True


def test_context_keeps_the_full_tool_output() -> None:
    full = "x" * 2000
    retained: dict[str, object] = {}
    messages, note = fit_messages(
        [{"role": "tool", "content": full}],
        max_tokens=100,
        retained=retained,
        tool_result_max_tokens=100,
        threshold=0.7,
    )
    assert note is not None
    content = str(messages[-1]["content"])
    assert "output_id=" in content
    output_id = content.split("output_id=", 1)[1].split(" ", 1)[0]
    assert read_output({"checkpoint": {"context": retained}}, output_id) == full
    assert retain_output(retained, "short")
