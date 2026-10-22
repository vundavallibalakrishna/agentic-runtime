"""Scheduled manifest drift check. Spec: docs/03-specs/08-tool-registry-mcp.md §8."""

from typing import TYPE_CHECKING

from ar_domain.tools.drift import check_drift

if TYPE_CHECKING:
    from typing import Any


def run_drift_check(store: Any) -> list[dict[str, object]]:
    """Re-discover approved servers. A changed manifest is never adopted."""
    return check_drift(store)
