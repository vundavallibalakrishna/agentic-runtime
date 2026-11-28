"""Ingest one document into chunks and the retrieval store.

Activities are idempotent. The dev API runs them inline; Temporal activities
call the same functions.
"""

import asyncio
import hashlib
import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.knowledge.boilerplate import block_settings, repeated_in_collection, without_repeated
from ar_domain.knowledge.chunker import chunk_markdown
from ar_domain.knowledge.embedding import embed_for_collection
from ar_domain.knowledge.index_text import indexed_text, passage_context
from ar_domain.knowledge.metrics import INGEST_DOCUMENTS, INGEST_STAGE
from ar_domain.knowledge.parse import ParseError, parse_bytes
from ar_domain.knowledge.store_types import IndexedChunk
from ar_domain.models.embedding import (
    EmbeddingFailedError,
    EmbeddingUnconfiguredError,
    refresh_registry,
)

if TYPE_CHECKING:
    from typing import Any


def max_bytes() -> int:
    from ar_common.settings import get_settings  # noqa: PLC0415

    return int(get_settings().ingest_max_bytes)


def ingest_document(store: Any, document_id: uuid.UUID, raw: bytes) -> str:
    """Parse, chunk, embed and index. Sync callers use this wrapper."""
    return str(_run(ingest_document_async(store, document_id, raw)))


async def ingest_document_async(store: Any, document_id: uuid.UUID, raw: bytes) -> str:
    """Parse, chunk, embed and index on the caller's event loop."""
    document = store.knowledge_documents.get(document_id)
    if not isinstance(document, dict):
        return "missing"
    digest = hashlib.sha256(raw).hexdigest()
    if document.get("version_hash") == digest and document.get("status") == "indexed":
        INGEST_DOCUMENTS.labels(kind="upload", result="unchanged").inc()
        return "unchanged"
    collection = store.knowledge_collections.get(document["collection_id"])
    if not isinstance(collection, dict):
        return "missing"
    document["status"] = "parsing"
    document["version_hash"] = digest
    document["size_bytes"] = len(raw)
    try:
        markdown = _parse(document, raw)
    except ParseError as exc:
        document["status"] = "failed"
        document["error"] = exc.code
        INGEST_DOCUMENTS.labels(kind="upload", result="failed").inc()
        return "failed"
    document["summary"] = _summary(markdown)
    document["status"] = "embedding"
    try:
        drafts, vectors, dropped = await _passages(
            store,
            collection,
            markdown,
            str(document["summary"]),
            title=str(document.get("title") or ""),
        )
        document["repeated_blocks_dropped"] = dropped
    except (EmbeddingUnconfiguredError, EmbeddingFailedError) as exc:
        # The document says why it is not searchable, and the caller is told the same.
        document["status"] = "failed"
        document["error"] = embedding_error(exc)
        INGEST_DOCUMENTS.labels(kind="upload", result="failed").inc()
        raise
    version = int(collection.get("index_version") or 1)
    await _replace_chunks(store, document, collection, (drafts, vectors), version)
    document["status"] = "indexed"
    document["indexed_at"] = utcnow()
    document["error"] = None
    _stats(store, collection)
    INGEST_DOCUMENTS.labels(kind="upload", result="indexed").inc()
    from ar_domain.routines.engine import on_document_changed  # noqa: PLC0415

    on_document_changed(store, document)
    return "indexed"


async def index_into_version(
    store: Any,
    document_id: uuid.UUID,
    raw: bytes,
    *,
    building: dict[str, object],
    version: int,
) -> None:
    """Write one document's passages into ``version``, built with ``building``'s settings.

    A re-index builds a new version of a collection's index while the version in use
    keeps answering. ``building`` is the collection as it will be once the new version is
    in use (its chunking, embedding model and physical collection). Every other version
    of the document's passages is left where it is, and the document row keeps saying
    what the version in use holds. It raises ``ParseError`` for bytes that cannot be read
    and the embedding errors for a model that cannot embed them.
    """
    document = store.knowledge_documents[document_id]
    # Parsing a large file (OCR of a scanned PDF) takes minutes of CPU. It runs off the
    # event loop, so the activity that called this can keep telling Temporal it is alive.
    markdown = await asyncio.to_thread(_parse, document, raw)
    drafts, vectors, dropped = await _passages(
        store, building, markdown, _summary(markdown), title=str(document.get("title") or "")
    )
    document["repeated_blocks_dropped"] = dropped
    await _replace_chunks(store, document, building, (drafts, vectors), version, keep_others=True)


def _parse(document: dict[str, object], raw: bytes) -> str:
    with INGEST_STAGE.labels(stage="parse").time():
        return parse_bytes(
            raw,
            mime_type=str(document.get("mime_type") or "text/markdown"),
            name=str(document.get("title") or "document.md"),
            max_bytes=max_bytes(),
        )


async def _passages(
    store: Any,
    collection: dict[str, object],
    markdown: str,
    summary: str,
    *,
    title: str = "",
) -> tuple[list[Any], list[list[float]], int]:
    """The passages of a document, their vectors, and how many repeated blocks were dropped.

    The stored passage is the passage itself. The vector is of the title, the heading
    path and the passage, so a section is found with the page it belongs to. A block
    that repeats across the collection is not part of either.
    """
    chunking = collection.get("chunking") if isinstance(collection.get("chunking"), dict) else {}
    target = int(chunking.get("target_tokens", 512)) if isinstance(chunking, dict) else 512
    overlap = int(chunking.get("overlap_pct", 12)) if isinstance(chunking, dict) else 12
    _share, min_chars = block_settings(collection)
    markdown, dropped = without_repeated(
        markdown, repeated_in_collection(store, collection), min_chars=min_chars
    )
    with INGEST_STAGE.labels(stage="chunk").time():
        drafts = chunk_markdown(markdown, target_tokens=target, overlap_pct=overlap)
    if not drafts and not dropped:
        drafts = chunk_markdown(markdown or summary or " ", target_tokens=target)
    texts = [indexed_text(title, list(draft.heading_path), draft.text) for draft in drafts]
    await refresh_registry(store)
    with INGEST_STAGE.labels(stage="embed").time():
        vectors = embed_for_collection(store, collection, texts)
    return drafts, vectors, dropped


def _inline_max_bytes() -> int:
    from ar_common.settings import get_settings  # noqa: PLC0415

    return int(get_settings().ingest_inline_max_bytes)


def stored_bytes(store: Any, document_id: uuid.UUID) -> bytes:
    """The bytes of the stored file a document was made from. Empty when there is none."""
    file_id = _stored_file(store, document_id)
    if not isinstance(file_id, uuid.UUID):
        return b""
    from ar_domain.durability.store import read_blob  # noqa: PLC0415

    return bytes(read_blob(store, file_id) or b"")


def _stored_file(store: Any, document_id: uuid.UUID) -> object:
    """The stored file a document was made from, when it was made from one."""
    document = getattr(store, "knowledge_documents", {}).get(document_id)
    return document.get("raw_file_id") if isinstance(document, dict) else None


async def ingest_or_enqueue(store: Any, document_id: uuid.UUID, raw: bytes) -> str:
    """Index here, or hand the file to the ingest worker when one is connected.

    A connected worker parses: its image has the layout parser and the converters, the
    API's has not, and reading a file there does not hold up the API. A small
    file travels with the request to the worker. A file over
    ``AR_INGEST_INLINE_MAX_BYTES`` is too large for that, so the worker reads it from
    the file store, where an upload already is. Only a large file that is in no file
    store is still parsed here.
    """
    client = getattr(store, "temporal_client", None)
    if (
        client is None
        or getattr(store, "_ingest_worker", False)
        or not hasattr(client, "start_workflow")
    ):
        return await ingest_document_async(store, document_id, raw)
    payload: dict[str, object] = {"document_id": str(document_id)}
    large = len(raw) > _inline_max_bytes()
    if not large:
        import base64  # noqa: PLC0415

        payload["raw_b64"] = base64.b64encode(raw).decode("ascii")
    elif _stored_file(store, document_id) is None:
        return await ingest_document_async(store, document_id, raw)
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_document  # noqa: PLC0415
    from ar_domain.durable.waiting import WORKER_WAIT_S, worker_result  # noqa: PLC0415

    await flush_store(store)
    digest = hashlib.sha256(raw).hexdigest()[:16]
    handle = await client.start_workflow(
        "IngestDocumentWorkflow",
        payload,
        id=f"ingest-{document_id}-{digest}",
        task_queue="ar-ingest",
    )
    try:
        finished, _answer = await worker_result(handle, WORKER_WAIT_S if large else 20)
    except Exception:  # the worker wrote the reason on the document
        await reload_document(store, document_id)
        raise_embedding_error(store.knowledge_documents.get(document_id))
        raise
    if not finished:
        if not large:
            return await ingest_document_async(store, document_id, raw)
        # The worker is still reading a large file. It finishes on its own; parsing the
        # same file here as well would only produce a second, poorer reading.
        await reload_document(store, document_id)
        waiting = store.knowledge_documents.get(document_id)
        return str(waiting.get("status") or "pending") if isinstance(waiting, dict) else "missing"
    await reload_document(store, document_id)
    document = store.knowledge_documents.get(document_id)
    if isinstance(document, dict):
        return str(document.get("status") or "indexed")
    return "missing"


_UNCONFIGURED = "embedding_unconfigured"
_FAILED = "embedding_failed"


def embedding_error(exc: EmbeddingUnconfiguredError | EmbeddingFailedError) -> str:
    """What a document records when its text could not be embedded."""
    code = _UNCONFIGURED if isinstance(exc, EmbeddingUnconfiguredError) else _FAILED
    return f"{code}: {exc.detail}"


def needs_admin(error: str) -> bool:
    """True when trying again cannot help until someone changes the Models screen."""
    return error.startswith(f"{_UNCONFIGURED}: ")


def raise_embedding_error(document: object) -> None:
    """Raise the embedding error a worker recorded on a document, if it recorded one."""
    error = str(document.get("error") or "") if isinstance(document, dict) else ""
    code, _, detail = error.partition(": ")
    if code == _UNCONFIGURED:
        raise EmbeddingUnconfiguredError(detail)
    if code == _FAILED:
        raise EmbeddingFailedError(detail)


def _index(store: Any) -> Any:
    from ar_domain.knowledge.store import active_index  # noqa: PLC0415

    return active_index(store)


async def _replace_chunks(
    store: Any,
    document: dict[str, object],
    collection: dict[str, object],
    passages: tuple[list[Any], list[list[float]]],
    version: int,
    *,
    keep_others: bool = False,
) -> None:
    """Put a document's passages into ``version`` of ``collection``'s index.

    An ingest replaces every version the document had. A re-index (``keep_others``)
    replaces only ``version``, so the version in use keeps its passages until the switch.
    """
    drafts, vectors = passages
    title = str(document.get("title") or "")
    document_id = document["id"]
    stale = [
        key
        for key, row in store.document_chunks.items()
        if row.get("document_id") == document_id
        and (not keep_others or int(row.get("index_version") or 1) == version)
    ]
    for key in stale:
        store.document_chunks.pop(key, None)
    if getattr(store, "durable", False):
        await _delete_stored_chunks(store, document_id, version if keep_others else None)
    name = str(collection.get("store_collection"))
    config = str(collection.get("text_search_config") or "simple")
    chunks: list[IndexedChunk] = []
    for draft, vector in zip(drafts, vectors, strict=False):
        chunk_id = uuid.uuid4()
        crumb = passage_context(title, list(draft.heading_path))
        lexical = indexed_text(title, list(draft.heading_path), draft.text)
        store.document_chunks[chunk_id] = {
            "id": chunk_id,
            "tenant_id": document["tenant_id"],
            "document_id": document_id,
            "ordinal": draft.ordinal,
            "text": draft.text,
            "context_prefix": crumb,
            "heading_path": list(draft.heading_path),
            "page_from": draft.page_from,
            "page_to": draft.page_to,
            "token_count": draft.token_count,
            "index_version": version,
            "embedding_model_id": collection.get("embedding_model_id"),
            "created_at": utcnow(),
        }
        chunks.append(
            IndexedChunk(
                chunk_id=chunk_id,
                tenant_id=document["tenant_id"],
                collection_id=document["collection_id"],
                document_id=document_id,
                source_id=document["source_id"],
                index_version=version,
                dense=vector,
                lexical_text=lexical,
                text_search_config=config,
                acl=list(document.get("acl_principals") or []),  # type: ignore[call-overload]
                classification=str(document.get("classification") or "internal"),
                mime_type=str(document.get("mime_type") or "text/markdown"),
                title=str(document.get("title") or ""),
                modified_at=None,
            )
        )
    if getattr(store, "durable", False):
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        await flush_store(store)
    index = _index(store)
    if keep_others:
        await index.delete(name, _delete_version(document, version))
    else:
        await index.delete(name, _delete_old(document, version))
    await index.upsert(name, chunks)


async def _delete_stored_chunks(
    store: Any, document_id: object, version: int | None = None
) -> None:
    """Drop a document's chunks so a re-ingest can insert the new ordinals.

    With ``version``, only that version's chunks go: a re-index leaves the one in use.
    """
    engine = getattr(store, "durable_engine", None)
    if engine is None:
        return
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415

    sql = "DELETE FROM document_chunks WHERE document_id = :id"
    params: dict[str, object] = {"id": document_id}
    if version is not None:
        sql += " AND index_version = :version"
        params["version"] = version
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await session.execute(text(sql), params)


def _delete_old(document: dict[str, object], version: int) -> Any:
    from ar_domain.knowledge.store_types import DeleteFilter  # noqa: PLC0415

    return DeleteFilter(
        tenant_id=document["tenant_id"],
        document_id=document["id"],
        index_version_ne=version,
    )


def _delete_version(document: dict[str, object], version: int) -> Any:
    from ar_domain.knowledge.store_types import DeleteFilter  # noqa: PLC0415

    return DeleteFilter(
        tenant_id=document["tenant_id"],
        document_id=document["id"],
        index_version=version,
    )


def _run(awaitable: Any) -> Any:
    from ar_domain.knowledge.syncutil import run_sync  # noqa: PLC0415

    return run_sync(awaitable)


def _summary(markdown: str) -> str:
    words = markdown.split()
    return " ".join(words[:200])


def _stats(store: Any, collection: dict[str, object]) -> None:
    """Count what the version of the index in use holds, not one a re-index is building."""
    version = int(collection.get("index_version") or 1)  # type: ignore[call-overload]
    documents = [
        row
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection.get("id") and row.get("status") != "deleted"
    ]
    chunks = [
        row
        for row in store.document_chunks.values()
        if row.get("document_id") in {item.get("id") for item in documents}
        and int(row.get("index_version") or 1) == version
    ]
    collection["stats"] = {
        "documents": len(documents),
        "chunks": len(chunks),
        "bytes": sum(int(row.get("size_bytes") or 0) for row in documents),
        "failed": sum(1 for row in documents if row.get("status") == "failed"),
        "repeated_blocks": sum(int(row.get("repeated_blocks_dropped") or 0) for row in documents),
    }
