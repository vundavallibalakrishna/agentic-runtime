"""Stage 5 files and judgements.

Original bytes stay in the object store. A judgement quotes a stored passage, or it
is not_supported, not_judged, or failed. Rule-set versions are immutable. OCR without
a reader is text_not_extracted. A chunk embedded by another model is HTTP 409.

Label: unit
"""

from __future__ import annotations

import uuid
from pathlib import Path

import orjson
import pytest

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.bundles.export import to_yaml
from ar_domain.documents.extract import ExtractError, unicode_text
from ar_domain.documents.judgement import judge_items
from ar_domain.documents.library import DocumentLibrary
from ar_domain.documents.ocr import VisionReader
from ar_domain.documents.originals import read_original
from ar_domain.documents.rules import export_rule_set, import_rule_set
from ar_domain.knowledge.embedding import refuse_embedding_mismatch
from ar_testing.objects import MemoryObjectStore

_EXAMPLE = (
    Path(__file__).resolve().parents[4] / "packs" / "examples" / "rule-sets" / "door-access.json"
)


def _actor(tenant: uuid.UUID | None = None) -> Actor:
    return Actor(
        tenant_id=tenant or uuid.uuid4(),
        user_id=uuid.uuid4(),
        permissions=frozenset({"chat:use"}),
    )


def _store() -> object:
    class Store:
        def __init__(self) -> None:
            self.scanner = "none"
            self.audit_log: list[dict[str, object]] = []
            self.objects = MemoryObjectStore()

    return Store()


def _document() -> dict[str, object]:
    return {
        "id": "doc-1",
        "content_hash": "abc",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Access",
                "text": "Staff use badges at every door.",
            }
        ],
    }


def test_ingest_keeps_original_bytes_and_citations_use_stored_passages() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    raw = b"# Access\n\nStaff use badges at every door.\n"
    saved = library.ingest(actor, data=raw, filename="access.md")
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]  # type: ignore[attr-defined]
    assert row["content_hash"]
    assert row["object_key"]
    assert read_original(store, str(row["object_key"])) == raw
    assert library.original(actor, document_id) == raw
    hits = library.search(actor, "badges")
    assert hits
    assert hits[0]["passage_id"] == hits[0]["anchor"]
    assert hits[0]["content_hash"] == row["content_hash"]
    assert "badges" in str(hits[0]["snippet"])


def test_a_quote_outside_the_passage_is_not_supported_and_overlap_is_not_judged() -> None:
    lexical = judge_items(
        _document(),
        [("badges", "Staff must use badges")],
        None,
        model_id="",
        rule_set_id="door-access",
        rule_set_version="1",
    )
    assert lexical[0]["verdict"] == "not_judged"
    assert lexical[0]["citation"] is None
    assert lexical[0]["prompt_hash"]

    def invented(_task: str, _evidence: str) -> str:
        return '{"verdict":"supported","passageId":"p1-s0","quote":"a colony on Mars"}'

    missed = judge_items(
        _document(),
        [("mars", "Operate a colony on Mars")],
        invented,
        model_id="model-1",
        rule_set_id="door-access",
        rule_set_version="1",
    )
    assert missed[0]["verdict"] == "not_supported"
    assert missed[0]["quote"] == ""
    assert missed[0]["model_id"] == "model-1"
    assert missed[0]["rule_set_id"] == "door-access"
    assert missed[0]["rule_set_version"] == "1"


def test_a_schema_failure_is_failed_and_a_real_quote_is_supported() -> None:
    def broken(_task: str, _evidence: str) -> str:
        return '{"verdict":"met","anchor":"p1-s0","quote":"Staff use badges"}'

    failed = judge_items(
        _document(),
        [("badges", "Staff use badges")],
        broken,
        model_id="model-1",
        rule_set_id="door-access",
        rule_set_version="1",
    )
    assert failed[0]["verdict"] == "failed"
    assert failed[0]["model_id"] == "model-1"
    assert failed[0]["prompt_hash"]

    def exact(_task: str, _evidence: str) -> str:
        return (
            '{"verdict":"supported","passageId":"p1-s0","quote":"Staff use badges at every door."}'
        )

    held = judge_items(
        _document(),
        [("badges", "Staff use badges at every door.")],
        exact,
        model_id="model-1",
        rule_set_id="door-access",
        rule_set_version="1",
    )
    assert held[0]["verdict"] == "supported"
    citation = held[0]["citation"]
    assert isinstance(citation, dict)
    assert citation["passage_id"] == "p1-s0"
    assert citation["quote"] in str(_document()["passages"][0]["text"])  # type: ignore[index]
    assert citation["content_hash"] == "abc"


def test_rule_set_versions_are_immutable_and_hidden_from_another_tenant() -> None:
    store = _store()
    actor = _actor()
    payload = orjson.loads(_EXAMPLE.read_bytes())
    imported = import_rule_set(store, actor, payload)
    assert imported["id"] == "door-access"
    assert imported["version"] == "1"
    again = import_rule_set(store, actor, payload)
    assert again["sha256"] == imported["sha256"]
    changed = dict(payload)
    changed["items"] = [{"itemId": "other", "statement": "Something else entirely."}]
    with pytest.raises(ConflictError):
        import_rule_set(store, actor, changed)
    exported = export_rule_set(store, actor, "door-access", "1")
    assert exported["items"][0]["statement"] == "Staff use badges at the door."
    stranger = _actor()
    with pytest.raises(NotFoundError):
        export_rule_set(store, stranger, "door-access", "1")
    assert any(row["action"] == "rule_set.imported" for row in store.audit_log)  # type: ignore[attr-defined]


def test_unicode_pdf_text_and_vision_without_a_model_is_not_live() -> None:
    assert unicode_text("Staff use badges.")
    assert not unicode_text("broken \ufffd text")
    reader = VisionReader(object(), uuid.uuid4())
    with pytest.raises(ExtractError) as caught:
        reader(b"\x89PNG\r\n\x1a\nnot-a-png")
    assert caught.value.code == "text_not_extracted"
    assert reader.proof == "unit"
    assert reader.model_id == ""
    with pytest.raises(ValidationFailedError):
        import_rule_set(_store(), _actor(), {"id": "empty", "version": "1", "items": []})


def test_an_embedding_model_mismatch_is_a_conflict() -> None:
    collection_id = uuid.uuid4()
    document_id = uuid.uuid4()
    current = uuid.uuid4()
    previous = uuid.uuid4()

    class Store:
        def __init__(self) -> None:
            self.knowledge_documents = {document_id: {"collection_id": collection_id}}
            self.document_chunks = {
                uuid.uuid4(): {
                    "document_id": document_id,
                    "embedding_model_id": previous,
                }
            }

    with pytest.raises(ConflictError):
        refuse_embedding_mismatch(
            Store(),
            [{"id": collection_id, "embedding_model_id": current}],
        )


def test_agent_yaml_omits_undefined_keys() -> None:
    text = to_yaml({"name": "Ada", "alias": None, "tools": [{"server": "files", "secret": None}]})
    assert "alias" not in text
    assert "secret" not in text
    assert "Ada" in text
