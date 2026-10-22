"""Ingest one document into chunks and the retrieval store.

Activities are idempotent. The dev API runs them inline; Temporal activities
call the same functions.
"""

import hashlib
import os
import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.knowledge.chunker import chunk_markdown
from ar_domain.knowledge.embedder import embed_texts
from ar_domain.knowledge.metrics import INGEST_DOCUMENTS, INGEST_STAGE
from ar_domain.knowledge.parse import ParseError, parse_bytes
from ar_domain.knowledge.store_types import IndexedChunk

if TYPE_CHECKING:
    from typing import Any


def max_bytes() -> int:
    raw = os.environ.get("AR_INGEST_MAX_BYTES", "209715200")
    try:
        return int(raw)
    except ValueError:
        return 209715200


def ingest_document(store: Any, document_id: uuid.UUID, raw: bytes) -> str:
    """Parse, chunk, embed and index. Returns the terminal status."""
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
        with INGEST_STAGE.labels(stage="parse").time():
            markdown = parse_bytes(
                raw,
                mime_type=str(document.get("mime_type") or "text/markdown"),
                name=str(document.get("title") or "document.md"),
                max_bytes=max_bytes(),
            )
    except ParseError as exc:
        document["status"] = "failed"
        document["error"] = exc.code
        INGEST_DOCUMENTS.labels(kind="upload", result="failed").inc()
        return "failed"
    document["summary"] = _summary(markdown)
    chunking = collection.get("chunking") if isinstance(collection.get("chunking"), dict) else {}
    target = int(chunking.get("target_tokens", 512)) if isinstance(chunking, dict) else 512
    overlap = int(chunking.get("overlap_pct", 12)) if isinstance(chunking, dict) else 12
    with INGEST_STAGE.labels(stage="chunk").time():
        drafts = chunk_markdown(markdown, target_tokens=target, overlap_pct=overlap)
    if not drafts:
        drafts = chunk_markdown(markdown or document["summary"] or " ", target_tokens=target)
    document["status"] = "embedding"
    prefix = ""
    if isinstance(chunking, dict) and chunking.get("contextual") is True:
        prefix = document["summary"][:400]
    texts = [
        "\n".join(part for part in (prefix, " / ".join(draft.heading_path), draft.text) if part)
        for draft in drafts
    ]
    dims = int(collection.get("dims") or 1024)
    model = str(collection.get("embedding_model") or "fake-embed")
    with INGEST_STAGE.labels(stage="embed").time():
        vectors = embed_texts(texts, model=model, dimensions=dims)
    index = _index(store)
    version = int(collection.get("index_version") or 1)
    _replace_chunks(store, document, drafts, vectors, prefix, version, index)
    document["status"] = "indexed"
    document["indexed_at"] = utcnow()
    document["error"] = None
    _stats(store, collection)
    INGEST_DOCUMENTS.labels(kind="upload", result="indexed").inc()
    return "indexed"


def _index(store: Any) -> Any:
    from ar_domain.knowledge.store import memory_index  # noqa: PLC0415

    return memory_index(store)


def _replace_chunks(  # noqa: PLR0917 - ingest writes every chunk field in one pass
    store: Any,
    document: dict[str, object],
    drafts: list[Any],
    vectors: list[list[float]],
    prefix: str,
    version: int,
    index: Any,
) -> None:
    document_id = document["id"]
    stale = [
        key for key, row in store.document_chunks.items() if row.get("document_id") == document_id
    ]
    for key in stale:
        store.document_chunks.pop(key, None)
    chunks: list[IndexedChunk] = []
    for draft, vector in zip(drafts, vectors, strict=False):
        chunk_id = uuid.uuid4()
        lexical = "\n".join(
            part for part in (prefix, " / ".join(draft.heading_path), draft.text) if part
        )
        store.document_chunks[chunk_id] = {
            "id": chunk_id,
            "tenant_id": document["tenant_id"],
            "document_id": document_id,
            "ordinal": draft.ordinal,
            "text": draft.text,
            "context_prefix": prefix,
            "heading_path": list(draft.heading_path),
            "page_from": draft.page_from,
            "page_to": draft.page_to,
            "token_count": draft.token_count,
            "index_version": version,
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
                text_search_config=str(
                    store.knowledge_collections[document["collection_id"]].get("text_search_config")
                    or "simple"
                ),
                acl=list(document.get("acl_principals") or []),  # type: ignore[call-overload]
                classification=str(document.get("classification") or "internal"),
                mime_type=str(document.get("mime_type") or "text/markdown"),
                title=str(document.get("title") or ""),
                modified_at=None,
            )
        )
    # The memory store is async; the inline pipeline runs it to completion.
    _run(
        index.delete(
            str(store.knowledge_collections[document["collection_id"]].get("store_collection")),
            _delete_old(document, version),
        )
    )
    _run(
        index.upsert(
            str(store.knowledge_collections[document["collection_id"]].get("store_collection")),
            chunks,
        )
    )


def _delete_old(document: dict[str, object], version: int) -> Any:
    from ar_domain.knowledge.store_types import DeleteFilter  # noqa: PLC0415

    return DeleteFilter(
        tenant_id=document["tenant_id"],
        document_id=document["id"],
        index_version_ne=version,
    )


def _run(awaitable: Any) -> Any:
    from ar_domain.knowledge.syncutil import run_sync  # noqa: PLC0415

    return run_sync(awaitable)


def _summary(markdown: str) -> str:
    words = markdown.split()
    return " ".join(words[:200])


def _stats(store: Any, collection: dict[str, object]) -> None:
    documents = [
        row
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection.get("id") and row.get("status") != "deleted"
    ]
    chunks = [
        row
        for row in store.document_chunks.values()
        if row.get("document_id") in {item.get("id") for item in documents}
    ]
    collection["stats"] = {
        "documents": len(documents),
        "chunks": len(chunks),
        "bytes": sum(int(row.get("size_bytes") or 0) for row in documents),
        "failed": sum(1 for row in documents if row.get("status") == "failed"),
    }
