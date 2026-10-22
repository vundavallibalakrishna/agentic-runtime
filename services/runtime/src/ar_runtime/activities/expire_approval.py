"""Expire or cancel one approval. Activities are idempotent. Spec: docs/03-specs/07-agent-runtime.md."""  # noqa: E501

import uuid

from temporalio import activity

_STORE: object | None = None


def bind_store(store: object) -> None:
    """Point activities at the process store for a test or a worker."""
    global _STORE  # noqa: PLW0603
    _STORE = store


def current_store() -> object | None:
    """The store bound for this process, or None."""
    return _STORE


@activity.defn(name="expire_approval")
async def expire_approval(approval_id: str) -> dict[str, str]:
    """Expire a pending approval. Repeating the call leaves a terminal row alone."""
    store = _STORE
    if store is not None and approval_id:
        from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

        ApprovalBook(store).expire_one(uuid.UUID(approval_id))
    return {"status": "expired", "approval_id": approval_id}


@activity.defn(name="cancel_approval")
async def cancel_approval(approval_id: str) -> dict[str, str]:
    """Cancel a pending approval. Repeating the call leaves a terminal row alone."""
    store = _STORE
    if store is not None and approval_id:
        from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

        ApprovalBook(store).cancel_one(uuid.UUID(approval_id))
    return {"status": "cancelled", "approval_id": approval_id}
