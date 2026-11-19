"""Run budgets, context assembly and callback signatures.

Spec: docs/03-specs/07-agent-runtime.md, docs/03-specs/20-notifications-events.md §3.1.
"""

from ar_domain.events.sign import sign_body

# The limits an agent runs under when its definition sets none. This is the one place
# that states them; the definition defaults, the built-in assistant and the agent loop
# all read it. An agent changes any of them in its own `budget`.
#
# `max_tokens` is counted as the first prompt, then what each later prompt adds, plus
# every step's output (OQ-88). The built-in assistant's first prompt is about 10,000
# tokens of instructions and tool descriptions, and each step's output is counted once
# as output and once more as part of the next prompt.
#
# The values fit each other (OQ-149). `max_tool_calls` equals `max_steps`, so the step
# limit is the one a run of single tool calls reaches. `max_wall_clock_s` is 16 model
# steps of up to 12 seconds (192) and 16 tool calls of about 25 seconds (400).
# `max_cost_micros` is a backstop: cost bills the whole prompt on every step, so 16
# steps under the token limit bill at most 16 x 80,000 input tokens, 3,840,000 micros
# at 3 per million. The cap sits just above that and stops a run only when a model
# costs more or an agent raised its other limits without raising this one.
DEFAULT_RUN_BUDGET: dict[str, int] = {
    "max_steps": 16,
    "max_tokens": 80_000,
    "max_cost_micros": 4_000_000,
    "max_wall_clock_s": 600,
    "max_tool_calls": 16,
    "max_parallel_tool_calls": 1,
}


def budget_exceeded(
    *,
    steps: int,
    tokens: int,
    cost_micros: int,
    elapsed_s: int,
    tool_calls: int,
    budget: dict[str, int],
) -> str | None:
    """Return the limit name when a budget is exceeded, else None."""
    checks = (
        ("max_steps", steps),
        ("max_tokens", tokens),
        ("max_cost_micros", cost_micros),
        ("max_wall_clock_s", elapsed_s),
        ("max_tool_calls", tool_calls),
    )
    for name, used in checks:
        if used > int(budget[name]):
            return name
    return None


def sign_run_callback(secret: str, body: bytes, timestamp: int) -> str:
    """Signature header value for a run callback. Same algorithm as webhooks."""
    return sign_body(secret, body, timestamp)


def tools_not_supported(definition: dict[str, object]) -> bool:
    """Tools run through the agent loop. The name stays for older callers."""
    del definition
    return False
