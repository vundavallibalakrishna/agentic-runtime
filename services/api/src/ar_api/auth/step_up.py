"""Step-up lifetime. Spec: docs/06-security/authn-authz.md §5."""

from datetime import datetime  # noqa: TC003

from ar_common.errors import ForbiddenError


def step_up_fresh(step_up_at: datetime | None, *, now: datetime, ttl_s: int) -> bool:
    """Return whether a session step-up is still inside its lifetime."""
    if step_up_at is None:
        return False
    return (now - step_up_at).total_seconds() <= ttl_s


def require_step_up(
    step_up_at: datetime | None, *, now: datetime, ttl_s: int, needed: bool
) -> None:
    """Raise when a session principal must step up and has not."""
    if needed and not step_up_fresh(step_up_at, now=now, ttl_s=ttl_s):
        raise ForbiddenError("step-up authentication is required")
