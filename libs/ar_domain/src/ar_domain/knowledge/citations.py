"""Citation indexes for one answer. Spec: docs/05-contracts/stream-events.md §7."""

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def allocate(hits: list[dict[str, object]], *, start: int = 1) -> list[dict[str, object]]:
    """Give each hit a stable index. Tool results and evidence items may omit documents."""
    citations: list[dict[str, object]] = []
    index = start
    for hit in hits:
        kind = str(hit.get("source_kind") or "knowledge")
        row: dict[str, object] = {
            "index": index,
            "source_kind": kind,
            "title": str(hit.get("title") or ""),
            "uri": str(hit.get("uri") or ""),
            "snippet": str(hit.get("snippet") or ""),
            "page_from": hit.get("page_from"),
            "page_to": hit.get("page_to"),
        }
        if kind == "knowledge":
            row["document_id"] = str(hit.get("document_id") or "")
            row["chunk_id"] = str(hit.get("chunk_id") or "")
            row["collection_id"] = str(hit.get("collection_id") or "")
        elif hit.get("evidence_id"):
            row["evidence_id"] = str(hit.get("evidence_id"))
        citations.append(row)
        index += 1
    return citations


def content_parts(text: str, citations: list[dict[str, object]]) -> list[dict[str, object]]:
    refs = [
        {"type": "citation_ref", "index": citation["index"], "citation": citation}
        for citation in citations
    ]
    return [{"type": "text", "text": text}, *refs]


def marker(index: int) -> str:
    return f"[{index}]"


def new_evidence(title: str, uri: str, snippet: str) -> dict[str, object]:
    return {
        "source_kind": "evidence_item",
        "evidence_id": str(uuid.uuid4()),
        "title": title,
        "uri": uri,
        "snippet": snippet,
    }


def as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    text = str(value or "")
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def public_citation(citation: dict[str, object]) -> dict[str, object]:
    """Fields the stream event and the message content share."""
    return {key: value for key, value in citation.items() if value is not None}


def tool_result_citation(title: str, uri: str, snippet: str) -> dict[str, object]:
    return {"source_kind": "tool_result", "title": title, "uri": uri, "snippet": snippet}


def known_indexes(citations: list[dict[str, object]]) -> set[int]:
    return {int(item["index"]) for item in citations if "index" in item}  # type: ignore[call-overload]


def readable(store: Any, actor: Any, citation: dict[str, object]) -> bool:
    """A knowledge citation resolves only when the person can read the document."""
    from ar_domain.knowledge.access import can_read_document, can_see  # noqa: PLC0415

    if str(citation.get("source_kind") or "knowledge") != "knowledge":
        return True
    document_id = as_uuid(citation.get("document_id"))
    if document_id is None:
        return False
    document = store.knowledge_documents.get(document_id)
    if not isinstance(document, dict):
        return False
    collection = store.knowledge_collections.get(document.get("collection_id"))
    if not isinstance(collection, dict) or not can_see(actor, collection):
        return False
    return can_read_document(store, actor, document, collection)
