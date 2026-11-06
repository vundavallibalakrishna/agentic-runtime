"""Add library documents, uploads, URLs and connections to a knowledge base.

Chunks keep the page and the section anchor. A document whose text has not
changed is left in place. Re-index replaces only that document's chunks.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.documents.chunk import RETRIEVAL_BUDGET
from ar_domain.knowledge.acl import collection_acl
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.chunker import ChunkDraft, chunk_markdown, token_count
from ar_domain.knowledge.embedding import embed_for_collection
from ar_domain.knowledge.pipeline import _stats
from ar_domain.knowledge.store import active_index
from ar_domain.knowledge.store_types import DeleteFilter, IndexedChunk
from ar_domain.models.embedding import refresh_registry

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_MAX_FETCH = 2_000_000


async def add_member(
    store: Any, actor: Actor, collection_id: uuid.UUID, body: dict[str, object]
) -> dict[str, object]:
    """Index one document into the collection. Unchanged text is not re-embedded."""
    await refresh_registry(store)
    book = KnowledgeBook(store)
    collection = book._managed(actor, collection_id)
    kind = str(body.get("kind") or "").strip().lower()
    force = bool(body.get("force"))
    if kind == "library":
        title, external_id, uri, passages = _from_library(store, actor, body)
    elif kind == "url":
        title, external_id, uri, passages = _from_url(store, body)
    elif kind == "connection":
        title, external_id, uri, passages = _from_connection(store, actor, body)
    elif kind in {"upload", "text"}:
        title, external_id, uri, passages = _from_text(body)
    else:
        raise ValidationFailedError("kind must be library, upload, url or connection")
    if not passages:
        raise ValidationFailedError("the document has no text to index")
    digest = hashlib.sha256("\n".join(item["text"] for item in passages).encode()).hexdigest()
    source = book._uploads(collection_id)
    existing = _find(store, collection_id, external_id)
    if (
        existing is not None
        and not force
        and existing.get("version_hash") == digest
        and existing.get("status") == "indexed"
    ):
        return {"document": book._document_view(existing), "result": "unchanged"}
    document = existing or _create_document(
        store, actor, collection, source, title=title, external_id=external_id, uri=uri
    )
    document["title"] = title
    document["uri"] = uri
    document["version_hash"] = digest
    document["status"] = "indexed"
    document["indexed_at"] = utcnow()
    document["error"] = None
    document["size_bytes"] = sum(len(item["text"]) for item in passages)
    document["summary"] = passages[0]["text"][:400]
    drafts = _drafts(passages)
    vectors = embed_for_collection(store, collection, [item.text for item in drafts])
    await _write_chunks(store, collection, document, drafts, vectors, passages=passages)
    _stats(store, collection)
    remember(
        store,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="document.added",
        target_type="knowledge_document",
        target_id=document["id"],
        detail={"collection_id": str(collection_id), "kind": kind, "chunks": len(drafts)},
    )
    return {"document": book._document_view(document), "result": "indexed", "chunks": len(drafts)}


async def refresh_document(store: Any, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
    """Re-index one document from its library row, URL or connection."""
    book = KnowledgeBook(store)
    document, collection = book._document(actor, document_id, manage=True)
    external = str(document.get("external_id") or "")
    uri = str(document.get("uri") or "")
    if external.startswith("library:"):
        body: dict[str, object] = {
            "kind": "library",
            "library_document_id": external.split(":", 1)[1],
            "force": True,
        }
    elif external.startswith("connection:"):
        body = {
            "kind": "connection",
            "connection_id": external.split(":", 1)[1],
            "url": uri,
            "title": document.get("title"),
            "force": True,
        }
    elif uri.startswith("http://") or uri.startswith("https://"):
        body = {"kind": "url", "url": uri, "title": document.get("title"), "force": True}
    else:
        raw = bytes(store.knowledge_blobs.get(document["id"], b""))
        if not raw:
            raise ValidationFailedError("this document has no stored text to re-index")
        body = {
            "kind": "text",
            "text": raw.decode("utf-8", errors="replace"),
            "title": document.get("title"),
            "external_id": external or str(document["id"]),
            "force": True,
        }
    return await add_member(store, actor, uuid.UUID(str(collection["id"])), body)


async def retrieve(
    store: Any,
    actor: Actor,
    collection_ids: list[uuid.UUID],
    query: str,
    *,
    top_k: int = 8,
) -> dict[str, object]:
    """Hybrid search trimmed to the prompt budget. The trace lists every chunk used."""
    from ar_domain.knowledge.searching import search_async  # noqa: PLC0415

    found = await search_async(
        store,
        actor,
        query=query,
        collection_ids=collection_ids,
        top_k=min(max(top_k, 1), 20),
        debug=True,
        min_score=0.05,
    )
    raw_hits = found.get("hits")
    hits = raw_hits if isinstance(raw_hits, list) else []
    kept: list[dict[str, object]] = []
    used = 0
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        text = str(hit.get("text") or hit.get("snippet") or "")
        if used and used + len(text) > RETRIEVAL_BUDGET:
            break
        used += len(text)
        kept.append(hit)
        if used >= RETRIEVAL_BUDGET:
            break
    model = ""
    if collection_ids:
        row = store.knowledge_collections.get(collection_ids[0])
        if isinstance(row, dict):
            model = str(row.get("embedding_model") or "")
    trace = {
        "query": query[:500],
        "collection_ids": [str(item) for item in collection_ids],
        "embedding_model": model,
        "rerank_model": str(found.get("rerank_model") or ""),
        "budget_chars": RETRIEVAL_BUDGET,
        "used_chars": used,
        "hits": [
            {
                "chunk_id": str(hit.get("chunk_id") or ""),
                "document_id": str(hit.get("document_id") or ""),
                "title": hit.get("title") or "",
                "anchor": hit.get("anchor") or "",
                "page": hit.get("page"),
                "heading": hit.get("heading") or "",
                "score": hit.get("rerank_score", hit.get("score")),
                "chars": len(str(hit.get("text") or hit.get("snippet") or "")),
                "snippet": str(hit.get("snippet") or "")[:500],
                "text": str(hit.get("text") or hit.get("snippet") or ""),
                "library_document_id": str(hit.get("library_document_id") or ""),
            }
            for hit in kept
        ],
    }
    return {"hits": kept, "answerable": bool(kept), "trace": trace}


def _from_library(
    store: Any, actor: Actor, body: dict[str, object]
) -> tuple[str, str, str, list[dict[str, str]]]:
    raw_id = body.get("library_document_id")
    try:
        document_id = uuid.UUID(str(raw_id))
    except ValueError as exc:
        raise ValidationFailedError("library_document_id is required") from exc
    row = store.library_documents.get(document_id)
    if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
        raise NotFoundError()
    passages = _passage_rows(row.get("passages"), title=str(row.get("title") or "Document"))
    return (
        str(row.get("title") or "Document"),
        f"library:{document_id}",
        f"library://{document_id}",
        passages,
    )


def _from_url(store: Any, body: dict[str, object]) -> tuple[str, str, str, list[dict[str, str]]]:
    url = str(body.get("url") or "").strip()
    text = _fetch(store, url, headers=None)
    title = str(body.get("title") or _title_from(text, url))
    return title, f"url:{hashlib.sha256(url.encode()).hexdigest()[:16]}", url, _plain(text, title)


def _from_connection(
    store: Any, actor: Actor, body: dict[str, object]
) -> tuple[str, str, str, list[dict[str, str]]]:
    from ar_domain.tools.service_connections import ConnectionBook, _headers  # noqa: PLC0415

    raw_id = body.get("connection_id")
    try:
        connection_id = uuid.UUID(str(raw_id))
    except ValueError as exc:
        raise ValidationFailedError("connection_id is required") from exc
    row = ConnectionBook(store)._own(actor, connection_id)
    url = str(body.get("url") or row.get("probe_url") or "").strip()
    headers, secret = _headers(row)
    text = _fetch(store, url, headers=headers)
    if secret and secret in text:
        text = text.replace(secret, "[redacted]")
    title = str(body.get("title") or row.get("name") or "Connection")
    return title, f"connection:{connection_id}", url, _plain(text, title)


def _from_text(body: dict[str, object]) -> tuple[str, str, str, list[dict[str, str]]]:
    text = str(body.get("text") or "").strip()
    if not text:
        raise ValidationFailedError("text is required")
    title = str(body.get("title") or "Note")
    external = str(body.get("external_id") or "")
    if not external:
        external = f"text:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    return title, external, f"text://{external}", _plain(text, title)


def _fetch(store: Any, url: str, headers: dict[str, str] | None) -> str:
    from ar_domain.tools.http_tools import fetch_text, guard_public  # noqa: PLC0415

    problem = guard_public(url, allow=["*"], loopback=False)
    if problem:
        raise ValidationFailedError(problem)
    sender = getattr(store, "http_send", None)
    if callable(sender):
        sent = sender("GET", url, headers=headers or {}, timeout=30)
        if isinstance(sent, tuple):
            status, text = int(sent[0]), str(sent[1])
        else:
            status, text = fetch_text(store, "GET", url, headers=headers, timeout=30)
    else:
        status, text = fetch_text(store, "GET", url, headers=headers, timeout=30)
    if status >= 400:
        raise ValidationFailedError(f"the URL returned {status}")
    if len(text) > _MAX_FETCH:
        text = text[:_MAX_FETCH]
    return text


def _plain(text: str, title: str) -> list[dict[str, str]]:
    cleaned = _SPACE.sub(" ", _TAG.sub(" ", text)).strip()
    if not cleaned:
        return []
    markdown = cleaned if cleaned.startswith("#") else f"# {title}\n\n{cleaned}"
    drafts = chunk_markdown(markdown, target_tokens=256, overlap_pct=12)
    passages: list[dict[str, str]] = []
    for draft in drafts:
        anchor = f"p{draft.page_from or 1}-{draft.ordinal}"
        heading = " / ".join(draft.heading_path)
        passages.append(
            {
                "text": draft.text,
                "anchor": anchor,
                "heading": heading,
                "page": str(draft.page_from or 1),
            }
        )
    return passages


def _passage_rows(value: object, *, title: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        page = item.get("page")
        page_text = str(page if isinstance(page, int) else 1)
        rows.append(
            {
                "text": text,
                "anchor": str(item.get("anchor") or f"p{page_text}"),
                "heading": str(item.get("heading") or title),
                "page": page_text,
            }
        )
    return rows


def _drafts(passages: list[dict[str, str]]) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for ordinal, item in enumerate(passages):
        try:
            page = int(item.get("page") or "1")
        except ValueError:
            page = 1
        heading = [part for part in item.get("heading", "").split(" / ") if part]
        drafts.append(
            ChunkDraft(
                ordinal=ordinal,
                text=item["text"],
                heading_path=heading,
                page_from=page,
                page_to=page,
                token_count=token_count(item["text"]),
            )
        )
    return drafts


def _find(store: Any, collection_id: uuid.UUID, external_id: str) -> dict[str, object] | None:
    for row in store.knowledge_documents.values():
        if (
            isinstance(row, dict)
            and row.get("collection_id") == collection_id
            and row.get("external_id") == external_id
            and row.get("status") != "deleted"
        ):
            return row
    return None


def _create_document(
    store: Any,
    actor: Actor,
    collection: dict[str, object],
    source: dict[str, object],
    *,
    title: str,
    external_id: str,
    uri: str,
) -> dict[str, object]:
    document_id = new_id()
    principals = collection_acl(
        visibility=str(collection.get("visibility") or "tenant"),
        owner_team_id=None
        if collection.get("owner_team_id") is None
        else str(collection.get("owner_team_id")),
        created_by=str(collection.get("created_by") or actor.user_id),
    )
    if collection.get("acl_mode") == "source":
        principals = [f"user:{actor.user_id}", "tenant:*"]
    now = utcnow()
    row = {
        "id": document_id,
        "tenant_id": actor.tenant_id,
        "collection_id": collection["id"],
        "source_id": source["id"],
        "external_id": external_id,
        "uri": uri,
        "title": title,
        "mime_type": "text/plain",
        "version_hash": "",
        "size_bytes": 0,
        "classification": str(collection.get("classification") or "internal"),
        "acl_principals": principals,
        "acl_hash": hashlib.sha256("|".join(sorted(principals)).encode()).hexdigest(),
        "summary": "",
        "status": "pending",
        "error": None,
        "indexed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    store.knowledge_documents[document_id] = row
    return row


async def _write_chunks(
    store: Any,
    collection: dict[str, object],
    document: dict[str, object],
    drafts: list[ChunkDraft],
    vectors: list[list[float]],
    *,
    passages: list[dict[str, str]],
) -> None:
    document_id = document["id"]
    stale = [
        key for key, row in store.document_chunks.items() if row.get("document_id") == document_id
    ]
    for key in stale:
        store.document_chunks.pop(key, None)
    raw_version = collection.get("index_version")
    version = raw_version if isinstance(raw_version, int) else 1
    indexed: list[IndexedChunk] = []
    for draft, vector, passage in zip(drafts, vectors, passages, strict=False):
        chunk_id = new_id()
        anchor = str(passage.get("anchor") or "")
        store.document_chunks[chunk_id] = {
            "id": chunk_id,
            "tenant_id": document["tenant_id"],
            "document_id": document_id,
            "ordinal": draft.ordinal,
            "text": draft.text,
            "context_prefix": f"anchor:{anchor}",
            "heading_path": list(draft.heading_path),
            "page_from": draft.page_from,
            "page_to": draft.page_to,
            "token_count": draft.token_count,
            "index_version": version,
            "created_at": utcnow(),
        }
        indexed.append(
            IndexedChunk(
                chunk_id=chunk_id,
                tenant_id=document["tenant_id"],
                collection_id=document["collection_id"],
                document_id=document_id,
                source_id=document["source_id"],
                index_version=version,
                dense=vector,
                lexical_text=draft.text,
                text_search_config=str(collection.get("text_search_config") or "simple"),
                acl=_principals(document.get("acl_principals")),
                classification=str(document.get("classification") or "internal"),
                title=str(document.get("title") or ""),
                modified_at=None,
            )
        )
    if getattr(store, "durable", False):
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        await flush_store(store)
    index = active_index(store)
    name = str(collection.get("store_collection") or "")
    await index.delete(
        name,
        DeleteFilter(
            tenant_id=document["tenant_id"],
            document_id=document_id,
            index_version_ne=version,
        ),
    )
    await index.upsert(name, indexed)


def _principals(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _title_from(text: str, url: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:120]
    return url[:120]
