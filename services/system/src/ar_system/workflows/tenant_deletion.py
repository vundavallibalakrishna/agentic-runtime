"""Tenant deletion steps. Spec: docs/03-specs/02-identity-tenancy.md §3.10."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeletionState:
    status: str
    resume: bool


def deletion_plan(*, grace_elapsed: bool, resumed: bool) -> DeletionState:
    """Deletion waits out the grace period unless an operator resumes the tenant."""
    if resumed:
        return DeletionState(status="active", resume=True)
    if not grace_elapsed:
        return DeletionState(status="deleting", resume=False)
    return DeletionState(status="deleted", resume=False)
