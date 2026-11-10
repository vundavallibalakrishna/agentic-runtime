"""Expire or cancel one approval. Activities are idempotent. Spec: docs/03-specs/07-agent-runtime.md."""  # noqa: E501

import uuid

from temporalio import activity

from ar_domain.readmodel.activity import repository_activity

_STORE: object | None = None


def bind_store(store: object) -> None:
    """Point activities at the process store for a test or a worker."""
    global _STORE  # noqa: PLW0603
    _STORE = store


def process_store() -> object | None:
    """The object boot bound. Ignores a request-scoped unit."""
    return _STORE


def current_store() -> object | None:
    """The unit for this activity, or the process store."""
    from ar_domain.readmodel.activity import active_unit  # noqa: PLC0415

    unit = active_unit()
    if unit is not None:
        return unit
    return _STORE


@activity.defn(name="expire_approval")
@repository_activity(process_store)
async def expire_approval(approval_id: str) -> dict[str, str]:
    """Expire a pending approval. Repeating the call leaves a terminal row alone."""
    store = current_store()
    if store is not None and approval_id:
        from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

        ApprovalBook(store).expire_one(uuid.UUID(approval_id))
    return {"status": "expired", "approval_id": approval_id}


@activity.defn(name="cancel_approval")
@repository_activity(process_store)
async def cancel_approval(approval_id: str) -> dict[str, str]:
    """Cancel a pending approval. Repeating the call leaves a terminal row alone."""
    store = current_store()
    if store is not None and approval_id:
        from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

        ApprovalBook(store).cancel_one(uuid.UUID(approval_id))
    return {"status": "cancelled", "approval_id": approval_id}
