"""Approval creation used by the gateway."""

from typing import TYPE_CHECKING

from ar_domain.approvals.service import ApprovalBook

if TYPE_CHECKING:
    from typing import Any


def book(store: Any) -> ApprovalBook:
    """Return the approval service for this process store."""
    return ApprovalBook(store)
