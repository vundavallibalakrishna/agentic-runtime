"""knowledge.search resolves a collection the model named, and never crashes on a bad id.

The model only sees a collection's name in its context, so it often passes a name (or a
slug, or a hallucinated id) where a uuid is expected. The tool handler must resolve any of
those and drop what it cannot, so the search falls back to every readable collection rather
than crashing with "badly formed hexadecimal UUID string".
"""

import uuid
from typing import TYPE_CHECKING

from ar_domain.tools.handlers import _resolve_collection_ids

if TYPE_CHECKING:
    import pytest


def _collection(name: str, slug: str) -> dict[str, object]:
    return {"id": str(uuid.uuid4()), "name": name, "slug": slug}


def test_resolves_a_uuid_a_slug_or_a_name_and_drops_the_rest() -> None:
    trust = _collection("ACME Trust Library", "acme-trust-library")
    policies = _collection("Policies", "policies")
    collections = [trust, policies]

    # A real uuid of a readable collection.
    assert _resolve_collection_ids([trust["id"]], collections) == [trust["id"]]
    # A slug.
    assert _resolve_collection_ids(["acme-trust-library"], collections) == [trust["id"]]
    # A name, case-insensitive — what the model most often passes.
    assert _resolve_collection_ids(["acme trust library"], collections) == [trust["id"]]
    # A hallucinated name or an id the person cannot read resolves to nothing, so the
    # handler then searches every readable collection instead of crashing.
    assert _resolve_collection_ids(["ACME trust library (v2)"], collections) == []
    assert _resolve_collection_ids([str(uuid.uuid4())], collections) == []
    assert _resolve_collection_ids(["not a uuid at all"], collections) == []
    # A mix keeps the ones that resolve, in order, without duplicates.
    assert _resolve_collection_ids(
        [trust["id"], "ACME Trust Library", "garbage", policies["slug"], trust["slug"]],
        collections,
    ) == [trust["id"], policies["id"]]
    # Anything that is not a list is ignored.
    assert _resolve_collection_ids("acme-trust-library", collections) == []
    assert _resolve_collection_ids(None, collections) == []


def _document(collection: str, title: str, uri: str, status: str = "indexed") -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "collection_id": uuid.UUID(collection),
        "title": title,
        "uri": uri,
        "status": status,
    }


class _Store:
    def __init__(self, *rows: dict[str, object]) -> None:
        self.knowledge_documents = {row["id"]: row for row in rows}


def test_a_document_is_named_the_way_a_passage_showed_it() -> None:
    from ar_domain.tools.handlers import _resolve_document_ids

    site = str(uuid.uuid4())
    other = str(uuid.uuid4())
    study = _document(site, "Case-Study.docx", "https://example.test/files/Case-Study.docx")
    page = _document(site, "Industries we serve", "https://example.test/industries/")
    gone = _document(site, "Old page", "https://example.test/old/", status="deleted")
    elsewhere = _document(other, "Case-Study.docx", "https://other.test/Case-Study.docx")
    store = _Store(study, page, gone, elsewhere)

    # The title a passage showed, in any case, and its address, even with a prefix the
    # model added of its own.
    assert _resolve_document_ids(["case-study.docx"], store, [site]) == [str(study["id"])]
    assert _resolve_document_ids(["site:https://example.test/industries/"], store, [site]) == [
        str(page["id"])
    ]
    assert _resolve_document_ids([str(page["id"])], store, [site]) == [str(page["id"])]
    # Only documents in the collections searched, and not deleted ones.
    assert _resolve_document_ids(["https://other.test/Case-Study.docx"], store, [site]) == []
    assert _resolve_document_ids(["Old page"], store, [site]) == []
    # A name nothing matches narrows nothing, so the search is not refused.
    assert _resolve_document_ids(["Annual report 2031"], store, [site]) == []
    assert _resolve_document_ids("Case-Study.docx", store, [site]) == []


def test_a_search_naming_a_document_by_title_is_narrowed_to_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler passes the resolved ids on, and searches everything when none resolve."""
    from ar_domain.tools import handlers

    site = uuid.uuid4()
    study = _document(str(site), "Case-Study.docx", "https://example.test/Case-Study.docx")
    sent: list[dict[str, object]] = []

    class _Book:
        def __init__(self, store: object) -> None:
            del store

        def list_collections(self, actor: object) -> list[dict[str, object]]:
            del actor
            return [{"id": site, "slug": "site", "name": "Site"}]

        def search(self, actor: object, body: dict[str, object]) -> dict[str, object]:
            del actor
            sent.append(body)
            return {"hits": [], "answerable": False}

    monkeypatch.setattr("ar_domain.knowledge.book.KnowledgeBook", _Book)
    store = _Store(study)
    for named in (["Case-Study.docx"], ["Not a document"]):
        handlers._knowledge(
            store,
            "search",
            {
                "query": "what changed",
                "document_ids": named,
                "_tenant_id": uuid.uuid4(),
                "_user_id": uuid.uuid4(),
            },
        )
    assert sent[0]["document_ids"] == [str(study["id"])]
    assert "document_ids" not in sent[1]
