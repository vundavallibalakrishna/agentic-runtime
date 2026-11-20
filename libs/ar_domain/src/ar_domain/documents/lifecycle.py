"""Delete a library document, and the vectors that were built from its bytes.

The same function removes a file the retention sweep has expired. A knowledge
document whose ``raw_file_id`` points at the file is deleted on the collection's
index, pgvector or Qdrant.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.audit.memory import remember
from ar_domain.knowledge.access import as_uuid

if TYPE_CHECKING:
    from typing import Any


def delete_library(store: Any, actor: Actor, document_id: uuid.UUID) -> None:
    """Remove one library row the caller owns, and the index built from it."""
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415

    library = DocumentLibrary(store)
    row = library._own(actor, document_id)
    if row.get("owner_user_id") != actor.user_id:
        raise NotFoundError()
    _drop_vectors(store, actor, row)
    store.library_documents.pop(document_id, None)
    remember(
        store,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="library_document.deleted",
        target_type="library_document",
        target_id=document_id,
        detail={"contentHash": str(row.get("content_hash") or "")},
    )


def delete_file_cascade(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, file_row: dict[str, object]
) -> None:
    """After a file is deleted, drop its extraction when no other file keeps the bytes."""
    digest = str(file_row.get("sha256") or "")
    if not digest:
        _drop_raw(store, file_row.get("id"), actor_id=user_id)
        return
    files = getattr(store, "files", {})
    others = (
        [
            row
            for row in files.values()
            if isinstance(row, dict)
            and row.get("tenant_id") == tenant_id
            and row.get("sha256") == digest
            and row.get("id") != file_row.get("id")
            and not row.get("deleted_at")
            and row.get("status") != "deleted"
        ]
        if isinstance(files, dict)
        else []
    )
    _drop_raw(store, file_row.get("id"), actor_id=user_id)
    if others:
        return
    documents = getattr(store, "library_documents", {})
    if not isinstance(documents, dict):
        return
    actor = Actor(tenant_id, user_id, frozenset({"chat:use"}))
    for document_id, row in list(documents.items()):
        if (
            isinstance(row, dict)
            and row.get("tenant_id") == tenant_id
            and row.get("content_hash") == digest
        ):
            try:
                delete_library(
                    store,
                    actor,
                    document_id if isinstance(document_id, uuid.UUID) else as_uuid(document_id),
                )
            except NotFoundError:
                documents.pop(document_id, None)


def sweep_expired(store: Any, *, now: object | None = None) -> int:
    """Delete files whose ``retention_until`` has passed. Returns how many."""
    moment = now or utcnow()
    files = getattr(store, "files", {})
    if not isinstance(files, dict):
        return 0
    removed = 0
    for file_id, row in list(files.items()):
        if not isinstance(row, dict) or row.get("deleted_at") or row.get("status") == "deleted":
            continue
        until = row.get("retention_until")
        if until is None or str(until) > str(moment):
            continue
        tenant = row.get("tenant_id")
        owner = row.get("owner_user_id")
        if not isinstance(tenant, uuid.UUID) or not isinstance(owner, uuid.UUID):
            continue
        row["status"] = "deleted"
        row["deleted_at"] = moment
        delete_file_cascade(store, tenant, owner, row)
        blobs = getattr(store, "blobs", None)
        if isinstance(blobs, dict):
            blobs.pop(file_id, None)
        removed += 1
    return removed


def reprocess(
    store: Any, actor: Actor, document_id: uuid.UUID, *, engine: str = ""
) -> dict[str, object]:
    """Read the stored original again and replace the passages."""
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415
    from ar_domain.documents.originals import read_original  # noqa: PLC0415

    library = DocumentLibrary(store)
    row = library._own(actor, document_id)
    if row.get("owner_user_id") != actor.user_id:
        raise NotFoundError()
    data = read_original(store, str(row.get("object_key") or ""))
    if not isinstance(data, bytes) or not data:
        raise NotFoundError()
    from typing import cast  # noqa: PLC0415

    from ar_domain.documents.extract import Ocr, extract_bytes  # noqa: PLC0415

    reader = _reader(store, actor, engine)
    extracted = extract_bytes(
        data,
        filename=str(row.get("filename") or "upload"),
        media_type=str(row.get("media_type") or ""),
        ocr=cast("Ocr | None", reader),
    )
    from ar_domain.documents.chunk import passage_dicts  # noqa: PLC0415
    from ar_domain.documents.quality import engine_name, quality_record  # noqa: PLC0415

    pages = extracted.metadata.get("pagesOcr")
    record = quality_record(
        page_count=extracted.page_count,
        passages=list(extracted.passages),
        tables=list(extracted.tables),
        pages_ocr=pages if isinstance(pages, int) and not isinstance(pages, bool) else 0,
        engine=str(
            extracted.metadata.get("ocrEngine") or (engine_name(reader) if reader else "none")
        ),
    )
    row["passages"] = passage_dicts(extracted.passages)
    row["tables"] = [
        {
            "anchor": table.anchor,
            "page": table.page,
            "caption": table.caption,
            "csv": table.csv_text,
        }
        for table in extracted.tables
    ]
    row["page_count"] = extracted.page_count
    row["status"] = "ready"
    row["error_code"] = None
    current = row.get("metadata")
    metadata = dict(current) if isinstance(current, dict) else {}
    metadata.update(record)
    row["metadata"] = metadata
    row["updated_at"] = utcnow()
    library._audit(
        actor,
        "library_document.ingested",
        document_id,
        {"filename": row.get("filename"), "reason": "reprocess"},
    )
    _reindex(store, actor, row)
    return library._view(row, detail=True)


def _drop_vectors(store: Any, actor: Actor, library_row: dict[str, object]) -> None:
    digest = str(library_row.get("content_hash") or "")
    files = getattr(store, "files", {})
    file_ids = (
        {
            row.get("id")
            for row in files.values()
            if isinstance(row, dict)
            and row.get("tenant_id") == actor.tenant_id
            and row.get("sha256") == digest
        }
        if isinstance(files, dict)
        else set()
    )
    documents = getattr(store, "knowledge_documents", {})
    if not isinstance(documents, dict):
        return
    from ar_domain.knowledge.syncing import delete_document  # noqa: PLC0415

    for document in list(documents.values()):
        if not isinstance(document, dict) or document.get("tenant_id") != actor.tenant_id:
            continue
        if document.get("status") == "deleted":
            continue
        if document.get("raw_file_id") in file_ids or (
            digest and str(document.get("version_hash") or "") == digest
        ):
            delete_document(store, document, actor_id=actor.user_id)


def _drop_raw(store: Any, file_id: object, *, actor_id: object) -> None:
    documents = getattr(store, "knowledge_documents", {})
    if not isinstance(documents, dict):
        return
    from ar_domain.knowledge.syncing import delete_document  # noqa: PLC0415

    for document in list(documents.values()):
        if (
            isinstance(document, dict)
            and document.get("raw_file_id") == file_id
            and document.get("status") != "deleted"
        ):
            delete_document(store, document, actor_id=actor_id)


def _reindex(store: Any, actor: Actor, library_row: dict[str, object]) -> None:
    """Start the existing ingest again when the file already sits in a collection."""
    documents = getattr(store, "knowledge_documents", {})
    if not isinstance(documents, dict):
        return
    digest = str(library_row.get("content_hash") or "")
    for document in documents.values():
        if not isinstance(document, dict) or document.get("tenant_id") != actor.tenant_id:
            continue
        if (
            str(document.get("version_hash") or "") != digest
            and document.get("raw_file_id") is None
        ):
            continue
        if str(document.get("version_hash") or "") != digest:
            linked = _file_hash(store, document.get("raw_file_id"))
            if linked != digest:
                continue
        from ar_domain.knowledge.pipeline import ingest_document_async  # noqa: PLC0415
        from ar_domain.knowledge.syncutil import run_sync  # noqa: PLC0415

        run_sync(ingest_document_async(store, as_uuid(document["id"]), _bytes(store, library_row)))
        return


def _file_hash(store: Any, file_id: object) -> str:
    files = getattr(store, "files", {})
    row = files.get(file_id) if isinstance(files, dict) else None
    return str(row.get("sha256") or "") if isinstance(row, dict) else ""


def _bytes(store: Any, library_row: dict[str, object]) -> bytes:
    from ar_domain.documents.originals import read_original  # noqa: PLC0415

    data = read_original(store, str(library_row.get("object_key") or ""))
    return data if isinstance(data, bytes) else b""


def _reader(store: Any, actor: Actor, engine: str) -> object | None:
    if engine == "vision":
        from ar_domain.documents.ocr import VisionReader  # noqa: PLC0415

        return VisionReader(store, actor.tenant_id)
    return None
