"""Audit export and chain verification. Spec: docs/03-specs/17-audit-usage-metering.md."""

from __future__ import annotations

import gzip
import hashlib
import io
from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import audit, own
from ar_domain.records.memory import blobs, bucket

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable

    from ar_domain.agents.access import Actor


class AuditExportBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def start(self, actor: Actor) -> dict[str, object]:
        rows = (
            row
            for row in self.store.audit_log
            if isinstance(row, dict) and str(row.get("tenant_id")) == str(actor.tenant_id)
        )
        export_id = new_id()
        payload = write_jsonl_gzip(rows)
        blobs(self.store, "audit_exports")[export_id] = payload
        row = {
            "id": export_id,
            "tenant_id": actor.tenant_id,
            "status": "ready",
            "bytes": len(payload),
            "created_at": utcnow(),
        }
        bucket(self.store, "audit_exports")[export_id] = row
        audit(
            self.store, actor, "audit.exported", "audit_export", export_id, {"bytes": len(payload)}
        )
        self._siem(actor)
        return {"id": str(export_id), "status": "ready", "bytes": len(payload)}

    def get(self, actor: Actor, export_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "audit_exports").get(export_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            raise NotFoundError()
        return {"id": str(row["id"]), "status": row["status"], "bytes": row["bytes"]}

    def _siem(self, actor: Actor) -> None:
        settings = getattr(self.store, "tenant_settings", {})
        row = settings.get(actor.tenant_id) if isinstance(settings, dict) else None
        audit_settings = row.get("audit") if isinstance(row, dict) else None
        siem = audit_settings.get("siem") if isinstance(audit_settings, dict) else None
        if not isinstance(siem, dict) or not siem.get("url"):
            return
        self.store.domain_events.append(
            {
                "topic": "audit.event",
                "payload": {"tenant_id": str(actor.tenant_id), "url": siem.get("url")},
                "at": utcnow().isoformat(),
            }
        )


def write_jsonl_gzip(rows: Iterable[dict[str, object]]) -> bytes:
    """Stream JSONL into gzip. Callers can pass a generator of any length."""
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
        for row in rows:
            handle.write(_line(row))
    return buffer.getvalue()


def verify_chain(rows: list[dict[str, object]]) -> bool:
    """True when each row's hash matches the previous row."""
    previous = ""
    for row in rows:
        body = f"{previous}|{row.get('action')}|{row.get('target_id')}"
        digest = hashlib.sha256(body.encode()).hexdigest()
        recorded = str(row.get("hash") or digest)
        if recorded != digest:
            return False
        previous = digest
    return True


def _line(row: dict[str, object]) -> bytes:
    import orjson  # noqa: PLC0415

    return orjson.dumps(row) + b"\n"
