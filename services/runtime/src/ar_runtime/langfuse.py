"""Langfuse metadata for one run. Content is included only when the tenant allows it.

Spec: docs/03-specs/18-observability-eval.md §1.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def trace_payload(
    run: Mapping[str, object],
    *,
    capture_content: bool,
    output: str = "",
) -> dict[str, object]:
    """Metadata always. The reply text only when capture_content is on."""
    payload: dict[str, object] = {
        "id": str(run.get("id") or ""),
        "name": "run",
        "model": str(run.get("model") or ""),
        "tokens_in": _int(run.get("tokens_in")),
        "tokens_out": _int(run.get("tokens_out")),
        "latency_ms": _int(run.get("latency_ms")),
        "tags": [f"tenant:{run.get('tenant_id') or ''}"],
    }
    if capture_content:
        payload["output"] = output
    return payload


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)
