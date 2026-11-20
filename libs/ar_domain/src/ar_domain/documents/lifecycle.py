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


def _owned(store: Any, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
    """The person's own library document that still has its original. Otherwise not found."""
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415

    row = DocumentLibrary(store)._own(actor, document_id)
    if row.get("owner_user_id") != actor.user_id or not row.get("object_key"):
        raise NotFoundError()
    return row


def reread(
    store: Any, actor: Actor, document_id: uuid.UUID, *, engine: str = ""
) -> dict[str, object]:
    """Read the stored original again and replace the passages. Returns the row.

    The layout parser reads first, as on an upload. A person who names the ``vision``
    engine asks for the pages to be read by the model, so that reading is used instead.
    """
    from typing import cast  # noqa: PLC0415

    from ar_domain.documents.chunk import passage_dicts  # noqa: PLC0415
    from ar_domain.documents.extract import ExtractError, Ocr, extract_bytes  # noqa: PLC0415
    from ar_domain.documents.layout import parse_layout  # noqa: PLC0415
    from ar_domain.documents.library import DocumentLibrary, _extract_error  # noqa: PLC0415
    from ar_domain.documents.originals import read_original  # noqa: PLC0415
    from ar_domain.documents.quality import engine_name, quality_record  # noqa: PLC0415

    library = DocumentLibrary(store)
    row = _owned(store, actor, document_id)
    data = read_original(store, str(row.get("object_key") or ""))
    if not isinstance(data, bytes) or not data:
        raise NotFoundError()
    reader = _reader(store, actor, engine)
    filename = str(row.get("filename") or "upload")
    media_type = str(row.get("media_type") or "")
    try:
        if reader is None:
            extracted = parse_layout(data, filename=filename, media_type=media_type)
        else:
            extracted = extract_bytes(
                data, filename=filename, media_type=media_type, ocr=cast("Ocr | None", reader)
            )
    except ExtractError as exc:
        # The earlier reading stays as it was.
        raise _extract_error(exc) from exc
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
    # Which reader made this reading: a note left by an earlier one does not describe it.
    metadata.pop("parser", None)
    metadata.pop("parserNote", None)
    metadata.update(extracted.metadata)
    metadata.update(record)
    row["metadata"] = metadata
    row["updated_at"] = utcnow()
    library._audit(
        actor,
        "library_document.ingested",
        document_id,
        {"filename": row.get("filename"), "reason": "reprocess"},
    )
    return row


def reprocess(
    store: Any, actor: Actor, document_id: uuid.UUID, *, engine: str = ""
) -> dict[str, object]:
    """Read the original again in this process, and index it again where it is in a collection."""
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415
    from ar_domain.knowledge.syncutil import run_sync  # noqa: PLC0415

    row = reread(store, actor, document_id, engine=engine)
    run_sync(_reindex(store, actor, row))
    return DocumentLibrary(store)._view(row, detail=True)


# How long a request waits for the worker to read the file again before it answers.
_WORKER_WAIT_S = 120


async def reprocess_document(
    store: Any, actor: Actor, document_id: uuid.UUID, *, engine: str = ""
) -> dict[str, object]:
    """Read a library document again: on the ingest worker when one is connected.

    The worker has the layout parser and the converters, and a long read there does not
    hold up the API. Without a worker the file is read in this process, off the loop.
    """
    import asyncio  # noqa: PLC0415

    from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415
    from ar_common.ids import new_id  # noqa: PLC0415
    from ar_common.offload import run_sync  # noqa: PLC0415
    from ar_domain.documents.library import (  # noqa: PLC0415
        DocumentLibrary,
        _install_library_row,
        _load_library_id,
    )
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

    row = _owned(store, actor, document_id)
    client = getattr(store, "temporal_client", None)
    if (
        client is None
        or getattr(store, "durable_engine", None) is None
        or not hasattr(client, "start_workflow")
        or getattr(store, "_ingest_worker", False)
    ):
        again: dict[str, object] = await run_sync(
            lambda: reprocess(store, actor, document_id, engine=engine)
        )
        return again
    await flush_store(store)
    handle = await client.start_workflow(
        "LibraryParseWorkflow",
        {
            "document_id": str(document_id),
            "tenant_id": str(actor.tenant_id),
            "reprocess": True,
            "engine": engine,
        },
        id=f"library-reprocess-{document_id}-{new_id()}",
        task_queue="ar-ingest",
    )
    library = DocumentLibrary(store)
    try:
        answer = await asyncio.wait_for(handle.result(), timeout=_WORKER_WAIT_S)
    except TimeoutError:
        # The worker is still reading. It finishes on its own; the row is as it was.
        return library._view(row, detail=True)
    if isinstance(answer, dict) and answer.get("status") == "failed":
        raise ArError(ErrorCode(str(answer.get("code"))), str(answer.get("message") or ""))
    loaded = await _load_library_id(store, actor.tenant_id, str(document_id))
    if loaded is not None:
        _install_library_row(store, loaded)
        row = loaded
    await _reindex(store, actor, row)
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


async def _reindex(store: Any, actor: Actor, library_row: dict[str, object]) -> None:
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
        from ar_domain.knowledge.pipeline import ingest_or_enqueue  # noqa: PLC0415

        # The same path an upload to a collection takes: the worker when one is connected.
        await ingest_or_enqueue(store, as_uuid(document["id"]), _bytes(store, library_row))
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
