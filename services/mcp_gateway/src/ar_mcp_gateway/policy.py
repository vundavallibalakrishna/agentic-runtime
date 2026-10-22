"""OPA client used by the gateway. Spec: docs/03-specs/09-policy-approvals.md §3."""

from typing import TYPE_CHECKING

from ar_domain.policy.engine import evaluate_call

if TYPE_CHECKING:
    from typing import Any


def decide(
    store: Any,
    request: dict[str, object],
    version: dict[str, object],
    tool: dict[str, object],
    server: dict[str, object],
) -> dict[str, object]:
    """Evaluate one call. An empty ``AR_OPA_URL`` uses the in-process rules."""
    return evaluate_call(store, request, version, tool, server)
