"""Append an audit row on the process store the audit API reads."""

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def remember(
    store: Any,
    *,
    tenant_id: object,
    actor_id: object,
    action: str,
    target_type: str,
    target_id: object,
    detail: dict[str, object],
    outcome: str = "success",
) -> None:
    """Record one state change. ``GET /api/v1/audit-events`` merges this log."""
    row = {
        "id": len(store.audit_log) + 1,
        "tenant_id": str(tenant_id),
        "actor_id": str(actor_id),
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id),
        "detail": detail,
        "outcome": outcome,
        "at": utcnow().isoformat(),
    }
    if isinstance(tenant_id, uuid.UUID):
        row["tenant_uuid"] = tenant_id
    store.audit_log.append(row)
