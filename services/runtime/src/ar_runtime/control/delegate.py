"""Delegation entry used by the runtime worker. Spec: docs/03-specs/07-agent-runtime.md §7."""

from typing import TYPE_CHECKING

from ar_domain.skills.delegate import delegate as run_delegate
from ar_domain.skills.delegate import plan_child

if TYPE_CHECKING:
    from typing import Any


def plan(payload: dict[str, object]) -> dict[str, object]:
    """Return the child plan, including a depth or budget refusal."""
    return plan_child(payload)


def delegate(
    store: Any, parent: dict[str, object], briefs: list[dict[str, object]]
) -> dict[str, object]:
    """Run delegations in process and roll usage up to the parent."""
    return run_delegate(store, parent, briefs)
