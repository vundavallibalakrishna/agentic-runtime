"""Gateway and process audit rows that belong on the hash chain.

``scripts/verify_audit_chain.py`` recomputes ``audit_events``. A row written by
``audit.service.record`` is covered. The in-memory double seals the same
document so a unit test can run the verifier without Postgres.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.audit.actions import AuditAction
from ar_domain.audit.chain import GENESIS
from ar_domain.audit.read import seal_chain_row
from ar_domain.durable.codec import as_uuid

if TYPE_CHECKING:
    from typing import Any

_KNOWN = {item.value for item in AuditAction}


def chain_candidates(rows: list[object]) -> list[dict[str, Any]]:
    """Catalogue actions that have a tenant. Unknown names stay off the chain."""
    chosen: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "")
        if action not in _KNOWN:
            continue
        tenant = as_uuid(row.get("tenant_uuid")) or as_uuid(row.get("tenant_id"))
        if tenant is None:
            continue
        chosen.append(row)
    return chosen


def seal_latest(store: object) -> None:
    """Link the newest process-log row onto ``audit_chain`` for the test double.

    A request-scoped unit skips this. Its commit calls ``audit.service.record``
    inside the same transaction as the change the row describes.
    """
    if getattr(store, "request_scoped", False):
        return
    log = getattr(store, "audit_log", None)
    if not isinstance(log, list) or not log:
        return
    pending = chain_candidates([log[-1]])
    if not pending:
        return
    row = pending[0]
    chain = getattr(store, "audit_chain", None)
    if not isinstance(chain, list):
        chain = []
        store.audit_chain = chain  # type: ignore[attr-defined]
    previous = str(chain[-1]["hash"]) if chain else GENESIS
    detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
    target = row.get("target_id")
    chain.append(
        seal_chain_row(
            seq=len(chain) + 1,
            prev_hash=previous,
            action=str(row.get("action") or ""),
            actor_id=str(row.get("actor_id") or ""),
            target_type=str(row.get("target_type") or "audit"),
            target_id=None if target in {None, ""} else str(target),
            outcome=str(row.get("outcome") or "success"),
            detail=detail,
            tenant_id=str(row.get("tenant_id") or "") or None,
        )
    )
