"""Per-field extraction and the field scorer.

Label: unit
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.documents.evidence import choose_strategy, interpret
from ar_domain.documents.extract import extract_bytes
from ar_domain.documents.library import (
    DocumentLibrary,
    _extraction_review_enabled,
    note_extraction_decision,
)
from ar_domain.evals.fields import fields_match, report
from ar_domain.evals.scoring import grade
from ar_testing.demo import demo_store

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "documents"


def test_an_extraction_review_uses_the_group_and_keeps_the_correction() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"documents": {"extractionReviewGroup": "reviewers"}}
    assert _extraction_review_enabled(store, tenant) is False
    actor = Actor(tenant, demo_id("admin"), frozenset())
    run_id = uuid.uuid4()
    body: dict[str, object] = {
        "exceptions": ["report_date"],
        "result": {"report_date": "old"},
        "fields": [],
    }
    DocumentLibrary(store)._review_extraction(
        actor, {"id": uuid.uuid4(), "metadata": {}}, {"type": "object"}, body, run_id=run_id
    )
    approval = next(iter(store.approvals.values()))
    assert approval["approver_rule"]["groups"] == ["reviewers"]
    assert approval["run_id"] == run_id
    extraction_id = uuid.uuid4()
    store.document_extractions[extraction_id] = {
        "id": extraction_id,
        "approval_id": approval["id"],
        "result": {"report_date": "old"},
        "corrections": [],
    }
    approval["status"] = "approved"
    approval["arguments"] = {"report_date": "new"}
    note_extraction_decision(store, approval)
    saved = store.document_extractions[extraction_id]
    assert saved["result"] == {"report_date": "new"}
    assert saved["corrections"][0]["diff"] == [
        {"path": "report_date", "before": "old", "after": "new"}
    ]
    assert store.audit_log[-1]["action"] == "extraction.corrected"


def test_parser_fallback_opens_a_review_when_review_is_opted_in() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"documents": {"extractionReview": True}}
    actor = Actor(tenant, demo_id("admin"), frozenset())
    body: dict[str, object] = {"exceptions": [], "result": {"note": "draft"}, "fields": []}
    DocumentLibrary(store)._review_extraction(
        actor,
        {"id": uuid.uuid4(), "metadata": {"parser": "fallback"}},
        {"type": "object", "properties": {"note": {"type": "string"}}},
        body,
    )
    assert store.approvals
    quiet = demo_store()
    DocumentLibrary(quiet)._review_extraction(
        actor,
        {"id": uuid.uuid4(), "metadata": {"parser": "docling"}},
        {"type": "object"},
        {"exceptions": [], "result": {}, "fields": []},
    )
    assert quiet.approvals == {}


def test_chunks_conflict_on_a_scalar_and_merge_array_items() -> None:
    from ar_domain.documents.evidence import merge_interpretations

    schema = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "findings": {"type": "array"},
        },
    }
    owner = {
        "path": "owner",
        "value": "Ada",
        "quote": "Ada",
        "quote_verified": True,
        "status": "extracted",
        "page": 1,
    }
    other = dict(owner)
    other["value"] = "Grace"
    first = {
        "path": "findings.0",
        "value": "leak",
        "quote": "leak",
        "quote_verified": True,
        "status": "extracted",
        "page": 1,
        "confidence": 0.9,
    }
    second = dict(first)
    second["path"] = "findings.0"
    second["value"] = "gap"
    second["page"] = 2
    repeat = dict(first)
    merged = merge_interpretations(
        [
            {"fields": [owner, first]},
            {"fields": [other, second, repeat]},
        ],
        schema,
        [],
    )
    by_path = {item["path"]: item for item in merged["fields"]}
    assert by_path["owner"]["status"] == "conflicting"
    assert by_path["findings.0"]["value"] == "leak"
    assert by_path["findings.0"]["page"] == 1
    assert by_path["findings.1"]["value"] == "gap"
    assert by_path["findings.1"]["page"] == 2
    assert "findings.2" not in by_path


def test_precision_counts_extra_fields_and_arrays_ignore_order() -> None:
    outcome = {"output_json": {"owner": "Ada", "extra": "no", "tags": ["b", "a"]}}
    item = {
        "type": "fields_match",
        "expected": {"owner": "Ada", "tags": ["a", "b"]},
        "normalisers": {"tags": "array"},
    }
    score = fields_match(item, outcome)
    assert score["passed"] is False
    assert score["precision"] < 1
    extras = [row for row in score["fields"] if row["normaliser"] == "extra"]
    assert extras and extras[0]["path"] == "extra"
    tags = next(row for row in score["fields"] if row["path"] == "tags")
    assert tags["match"] is True


def test_a_quote_in_the_source_is_extracted_and_a_missing_one_is_not() -> None:
    passages = [{"text": "The report date is 4 March 2026.", "page": 1, "anchor": "p1"}]
    raw = (
        '{"fields": {"report_date": {"value": "4 March 2026", "quote": "4 March 2026", '
        '"locator": "p1", "page": 1, "confidence": 0.95}, '
        '"owner": {"value": "someone else", "quote": "not in the page", "confidence": 0.9}}}'
    )
    schema = {
        "type": "object",
        "required": ["report_date", "owner"],
        "properties": {"report_date": {"type": "string"}, "owner": {"type": "string"}},
    }
    body = interpret(raw, schema, passages, threshold=0.8)
    by_path = {item["path"]: item for item in body["fields"]}
    assert by_path["report_date"]["status"] == "extracted"
    assert by_path["report_date"]["quote_verified"] is True
    assert by_path["owner"]["status"] == "missing"
    assert by_path["owner"]["quote_verified"] is False
    assert "owner" in body["exceptions"]


def test_a_wrong_type_or_a_value_absent_from_its_quote_is_invalid() -> None:
    passages = [{"text": "The limit is one thousand.", "page": 1, "anchor": "p1"}]
    typed = interpret(
        '{"fields": {"limit": {"value": "1000", "quote": "one thousand", "confidence": 0.9}}}',
        {"type": "object", "properties": {"limit": {"type": "integer"}}},
        passages,
    )
    assert typed["fields"][0]["status"] == "invalid"
    unsupported = interpret(
        '{"fields": {"limit": {"value": "1000", "quote": "one thousand", "confidence": 0.9}}}',
        {"type": "object", "properties": {"limit": {"type": "string"}}},
        passages,
    )
    assert unsupported["fields"][0]["status"] == "invalid"
    assert "limit" in unsupported["exceptions"]


def test_normalised_numbers_dates_and_booleans_count_as_supported() -> None:
    passages = [
        {
            "text": "Amount 1,500 is due on 15 January 2026. Approved: Yes. Flag: No.",
            "page": 1,
            "anchor": "p1",
        }
    ]
    schema = {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "when": {"type": "string"},
            "approved": {"type": "boolean"},
            "flag": {"type": "boolean"},
            "wrong": {"type": "number"},
            "other_day": {"type": "string"},
        },
    }
    raw = (
        '{"fields": {'
        '"amount": {"value": 1500.0, "quote": "1,500", "confidence": 0.95}, '
        '"when": {"value": "2026-01-15", "quote": "15 January 2026", "confidence": 0.95}, '
        '"approved": {"value": true, "quote": "Yes", "confidence": 0.95}, '
        '"flag": {"value": false, "quote": "No", "confidence": 0.95}, '
        '"wrong": {"value": 1501, "quote": "1,500", "confidence": 0.95}, '
        '"other_day": {"value": "2026-01-16", "quote": "15 January 2026", "confidence": 0.95}'
        "}}"
    )
    body = interpret(raw, schema, passages, threshold=0.8)
    by_path = {item["path"]: item for item in body["fields"]}
    assert by_path["amount"]["status"] == "extracted"
    assert by_path["when"]["status"] == "extracted"
    assert by_path["approved"]["status"] == "extracted"
    assert by_path["flag"]["status"] == "extracted"
    assert by_path["wrong"]["status"] == "invalid"
    assert by_path["other_day"]["status"] == "invalid"


def test_a_low_confidence_quote_is_not_extracted() -> None:
    passages = [{"text": "Limit 1000", "page": 2, "anchor": "p2"}]
    raw = '{"fields": {"limit": {"value": "1000", "quote": "1000", "confidence": 0.2}}}'
    body = interpret(
        raw,
        {"type": "object", "properties": {"limit": {"type": "string"}}},
        passages,
        threshold=0.8,
    )
    assert body["fields"][0]["status"] == "low_confidence"


def test_strategy_follows_the_measured_window() -> None:
    short = "one two"
    assert choose_strategy(short, 100_000) == "single"
    assert choose_strategy(short * 5000, 50) == "map"


def test_fields_match_normalises_dates_numbers_and_names() -> None:
    outcome = {
        "output_text": '{"when": "4 March 2026", "amount": "1,000", "owner": "Ada  Lovelace"}'
    }
    item = {
        "type": "fields_match",
        "document_type": "sample",
        "expected": {"when": "2026-03-04", "amount": 1000, "owner": "ada lovelace"},
        "normalisers": {"when": "date", "amount": "number", "owner": "name"},
    }
    score = fields_match(item, outcome)
    assert score["passed"] is True
    graded = grade([item], outcome)
    assert graded["fields_match_0"]["passed"] is True
    summary = report([score])
    assert summary["by_document_type"]["sample"]["recall"] == 1.0


def test_two_chunks_merge_and_a_msg_without_a_worker_is_a_clear_error() -> None:
    from ar_domain.documents.evidence import chunks_for, merge_interpretations

    passages = [
        {"text": "alpha " * 40, "page": 1, "anchor": "p1"},
        {"text": "beta " * 40, "page": 2, "anchor": "p2"},
    ]
    groups = chunks_for(passages, 30)
    assert len(groups) >= 2
    schema = {"type": "object", "properties": {"note": {"type": "string"}}}
    merged = merge_interpretations(
        [
            {
                "fields": [
                    {
                        "path": "note",
                        "value": "alpha",
                        "quote": "alpha",
                        "quote_verified": True,
                        "status": "extracted",
                    }
                ]
            },
            {
                "fields": [
                    {
                        "path": "note",
                        "value": "alpha",
                        "quote": "alpha",
                        "quote_verified": True,
                        "status": "extracted",
                    }
                ]
            },
        ],
        schema,
        passages,
    )
    assert merged["fields"][0]["value"] == "alpha"
    from ar_domain.documents.convert import convert_and_extract
    from ar_domain.documents.extract import ExtractError

    with pytest.raises(ExtractError, match="ingest worker"):
        convert_and_extract(b"not a message", "note.msg", "")


def test_fixture_pdfs_are_real_files() -> None:
    text = (FIXTURES / "synthetic-report.pdf").read_bytes()
    scanned = (FIXTURES / "synthetic-scan.pdf").read_bytes()
    assert text.startswith(b"%PDF")
    assert scanned.startswith(b"%PDF")
    reading = extract_bytes(text, filename="synthetic-report.pdf")
    joined = "\n".join(item.text for item in reading.passages)
    assert "SYNTHETIC-REPORT-REF" in joined
    scanned_reading = extract_bytes(scanned, filename="synthetic-scan.pdf")
    scanned_text = "\n".join(item.text for item in scanned_reading.passages)
    assert "SCANNED" in scanned_text.upper()
