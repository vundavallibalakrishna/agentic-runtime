"""A library hit always names a library document and one of its passages.

Certification runs 7 to 10: ``research.search`` found no library passage although the
document was in the library. The same bytes had also been ingested into a knowledge
collection, so the index answered with the knowledge document's id and no anchor, and
research could not open the address it built from them.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

from ar_domain.agents.access import Actor
from ar_domain.documents.library import DocumentLibrary
from ar_domain.research import providers

if TYPE_CHECKING:
    import pytest

_TENANT = uuid.uuid4()
_USER = uuid.uuid4()
_BREAK_GLASS = "Break-glass access is allowed for 4 hours and must be approved by the duty manager."
_RETENTION = "Access logs are kept for 7 years."


def _store() -> tuple[SimpleNamespace, uuid.UUID, uuid.UUID]:
    """One library document, and a knowledge document holding the same bytes."""
    library_id, knowledge_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store = SimpleNamespace(
        library_documents={
            library_id: {
                "id": library_id,
                "tenant_id": _TENANT,
                "owner_user_id": _USER,
                "title": "Access control policy",
                "status": "ready",
                "content_hash": "same-bytes",
                "passages": [
                    {"anchor": "p1", "text": _BREAK_GLASS},
                    {"anchor": "p2", "text": _RETENTION},
                ],
            }
        },
        knowledge_documents={
            knowledge_id: {
                "id": knowledge_id,
                "tenant_id": _TENANT,
                "status": "indexed",
                "collection_id": uuid.uuid4(),
                "version_hash": "same-bytes",
                "external_id": "upload:policy.md",
                "title": "policy.md",
            }
        },
        document_chunks={
            chunk_id: {"id": chunk_id, "document_id": knowledge_id, "text": _BREAK_GLASS}
        },
        files={},
        tenant_settings={},
    )
    return store, library_id, knowledge_id


def _index_answers(monkeypatch: pytest.MonkeyPatch, knowledge_id: uuid.UUID) -> None:
    """The index's answer for a chunk the ingest pipeline wrote: no anchor, no library id."""

    def search(_store: object, _actor: object, **_asked: object) -> dict[str, object]:
        return {
            "hits": [
                {
                    "document_id": knowledge_id,
                    "title": "policy.md",
                    "snippet": _BREAK_GLASS,
                    "text": _BREAK_GLASS,
                    "anchor": "",
                    "library_document_id": "",
                    "score": 0.9,
                }
            ]
        }

    monkeypatch.setattr("ar_domain.knowledge.searching.search", search)
    monkeypatch.setattr("ar_domain.knowledge.threshold.retrieval_bar", lambda *_a: 0.0)


def test_an_index_hit_is_placed_on_the_library_document_and_its_passage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, library_id, knowledge_id = _store()
    _index_answers(monkeypatch, knowledge_id)
    reader = Actor(tenant_id=_TENANT, user_id=_USER, permissions=frozenset({"chat:use"}))
    found = DocumentLibrary(store).search(reader, "break-glass approval duty manager")
    [hit] = found["hits"]  # type: ignore[misc]
    assert hit["document_id"] == str(library_id)
    assert hit["anchor"] == "p1"


def test_research_can_open_the_passage_it_found(monkeypatch: pytest.MonkeyPatch) -> None:
    store, library_id, knowledge_id = _store()
    _index_answers(monkeypatch, knowledge_id)
    hits = providers.library_hits(
        store, _TENANT, "break-glass approval duty manager", limit=4, user_id=_USER
    )
    assert [row["url"] for row in hits] == [f"library://{library_id}#p1"]
    assert providers.library_page(store, _TENANT, hits[0]["url"]) == _BREAK_GLASS
