"""The passages an answer cites from the files attached to its conversation.

A document tool and the attachment excerpt both show a passage after its anchor, such as
``[p1-s0 p.1]``. When the answer repeats an anchor, the passage becomes a citation part, so
the chat draws a source chip and an API caller gets the passage, its page and its document.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from ar_domain.files.attachments import conversation_attachments

if TYPE_CHECKING:
    from typing import Any

# An anchor as the tools print it, with or without the page after it.
_ANCHOR = re.compile(r"\[(p\d+-[a-z]*\d+(?:-\d+)?)\b")
_WORD = re.compile(r"[a-z0-9]{4,}")
_SNIPPET = 280


def passage_line(passage: dict[str, object]) -> str:
    """One passage the way a prompt shows it: its anchor and page, then its text."""
    return f"[{passage.get('anchor')} p.{passage.get('page')}] {passage.get('text')}"


def cited_parts(
    store: Any, run: dict[str, object], answer: str, *, start: int = 1
) -> list[dict[str, object]]:
    """A citation part for each anchor in ``answer`` that an attached document holds."""
    anchors = list(dict.fromkeys(_ANCHOR.findall(answer)))
    if not anchors:
        return []
    documents = _attached_documents(store, run)
    words = set(_WORD.findall(answer.lower()))
    parts: list[dict[str, object]] = []
    for anchor in anchors:
        found = _passage(documents, anchor, words)
        if found is None:
            continue
        document, passage = found
        index = start + len(parts)
        document_id = str(document.get("id") or "")
        parts.append(
            {
                "type": "citation_ref",
                "index": index,
                "citation": {
                    "index": index,
                    "source_kind": "document",
                    "title": str(document.get("title") or document.get("filename") or "Source"),
                    "snippet": str(passage.get("text") or "")[:_SNIPPET],
                    "uri": f"/documents/{document_id}#{anchor}",
                    "document_id": document_id,
                    "anchor": anchor,
                    "page": passage.get("page"),
                },
            }
        )
    return parts


def _attached_documents(store: Any, run: dict[str, object]) -> list[dict[str, object]]:
    library = getattr(store, "library_documents", None)
    if not isinstance(library, dict):
        return []
    rows: list[dict[str, object]] = []
    for item in conversation_attachments(store, run.get("conversation_id")):
        row = library.get(item.document_id) if isinstance(item.document_id, uuid.UUID) else None
        if isinstance(row, dict) and row.get("tenant_id") == run.get("tenant_id"):
            rows.append(row)
    return rows


def _passage(
    documents: list[dict[str, object]], anchor: str, words: set[str]
) -> tuple[dict[str, object], dict[str, object]] | None:
    """The passage with this anchor. Two attached files may both have one: the passage
    that shares the most words with the answer is the one it cites."""
    best: tuple[dict[str, object], dict[str, object]] | None = None
    score = -1
    for document in documents:
        passages = document.get("passages")
        for passage in passages if isinstance(passages, list) else []:
            if not isinstance(passage, dict) or str(passage.get("anchor") or "") != anchor:
                continue
            shared = len(words & set(_WORD.findall(str(passage.get("text") or "").lower())))
            if shared > score:
                best, score = (document, passage), shared
    return best
