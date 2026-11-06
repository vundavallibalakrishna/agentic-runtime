"""Run budgets, context assembly and callback signatures.

Spec: docs/03-specs/07-agent-runtime.md, docs/03-specs/20-notifications-events.md §3.1.
"""

from ar_domain.events.sign import sign_body


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
