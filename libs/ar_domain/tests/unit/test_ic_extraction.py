"""Per-field extraction and the field scorer.

Label: unit
"""

from __future__ import annotations

from pathlib import Path

from ar_domain.documents.evidence import choose_strategy, interpret
from ar_domain.documents.extract import extract_bytes
from ar_domain.evals.fields import fields_match, report
from ar_domain.evals.scoring import grade

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "documents"


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


def test_fixture_pdfs_are_real_files() -> None:
    from ar_domain.documents.extract import ExtractError

    text = (FIXTURES / "synthetic-report.pdf").read_bytes()
    scanned = (FIXTURES / "synthetic-scan.pdf").read_bytes()
    assert text.startswith(b"%PDF")
    assert scanned.startswith(b"%PDF")
    reading = extract_bytes(text, filename="synthetic-report.pdf")
    joined = "\n".join(item.text for item in reading.passages)
    assert "SYNTHETIC-REPORT-REF" in joined
    try:
        scanned_reading = extract_bytes(scanned, filename="synthetic-scan.pdf")
    except ExtractError as exc:
        message = exc.message
    else:
        scanned_text = "\n".join(item.text for item in scanned_reading.passages)
        assert "SCANNED" in scanned_text.upper()
        return
    assert "OCR" in message or "Unicode" in message
