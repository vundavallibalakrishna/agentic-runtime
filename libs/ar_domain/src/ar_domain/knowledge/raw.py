"""Where a knowledge document's fetched bytes live, and the versions it has had.

Each body a source sync fetches is stored as a file (``kind = knowledge_raw``) in the
object store, the document points at the newest one (``raw_file_id``), and a
``document_revisions`` row records every one. Nothing is overwritten: the versions of a
document can be listed and each one's bytes read back.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.files.logic import object_key

if TYPE_CHECKING:
    from typing import Any


def keep_raw(
    store: Any,
    document: dict[str, object],
    raw: bytes,
    *,
    mime_type: str,
    measured: dict[str, object] | None = None,
) -> uuid.UUID:
    """Store ``raw`` as this document's newest version and return its file id.

    The same bytes as the version the document already points at are not stored twice.
    """
    from ar_domain.files.objects import keep_bytes  # noqa: PLC0415

    digest = hashlib.sha256(raw).hexdigest()
    current = _file(store, document.get("raw_file_id"))
    if current is not None and current.get("sha256") == digest:
        return uuid.UUID(str(current["id"]))
    file_id = new_id()
    now = utcnow()
    tenant = document["tenant_id"]
    row: dict[str, object] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": None,
        "conversation_id": None,
        "run_id": None,
        "kind": "knowledge_raw",
        "name": str(document.get("title") or "document")[:240],
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": len(raw),
        "sha256": digest,
        "object_key": object_key(
            str(tenant), "knowledge_raw", f"{now:%Y}", f"{now:%m}", str(file_id)
        ),
        "classification": str(document.get("classification") or "internal"),
        "status": "ready",
        "scan_status": "skipped",
        "preview": {},
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    keep_bytes(store, row, raw)
    store.files[file_id] = row
    document["raw_file_id"] = file_id
    revision_id = new_id()
    _revisions(store)[revision_id] = {
        "id": revision_id,
        "tenant_id": tenant,
        "document_id": document["id"],
        "file_id": file_id,
        "version_hash": digest,
        "size_bytes": len(raw),
        "metadata": dict(measured or {}),
        "captured_at": now,
    }
    return file_id


def revisions_of(store: Any, document_id: object) -> list[dict[str, object]]:
    """The versions a document has had, newest first."""
    rows = [
        row
        for row in _revisions(store).values()
        if isinstance(row, dict) and str(row.get("document_id")) == str(document_id)
    ]
    rows.sort(key=lambda item: str(item.get("captured_at") or ""), reverse=True)
    return rows


def _revisions(store: Any) -> dict[Any, Any]:
    rows = getattr(store, "document_revisions", None)
    if not isinstance(rows, dict):
        rows = {}
        store.document_revisions = rows
    return rows


def _file(store: Any, file_id: object) -> dict[str, object] | None:
    files = getattr(store, "files", None)
    if not isinstance(files, dict) or file_id is None:
        return None
    row = files.get(file_id)
    if row is None and isinstance(file_id, str):
        try:
            row = files.get(uuid.UUID(file_id))
        except ValueError:
            return None
    return row if isinstance(row, dict) and not row.get("deleted_at") else None
