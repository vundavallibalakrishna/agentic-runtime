"""Passages are embedded with their document title and heading path."""

from ar_domain.knowledge.index_text import (
    INDEX_TEXT_VERSION,
    indexed_text,
    passage_context,
    text_version,
)


def test_the_indexed_text_leads_with_the_title_and_the_heading_path() -> None:
    body = "The desk opens at 08:30."
    indexed = indexed_text("Visitor guide", ["Hours", "Desk"], body)
    assert indexed.startswith("Visitor guide / Hours / Desk\n")
    assert indexed.endswith(body)
    assert passage_context("Visitor guide", ["Visitor guide", "Hours"]) == "Visitor guide / Hours"


def test_the_stored_passage_is_not_the_indexed_text() -> None:
    body = "Only the passage."
    assert body not in passage_context("Guide", ["Hours"])
    assert indexed_text("Guide", ["Hours"], body) != body


def test_a_collection_without_a_stamp_is_the_previous_text() -> None:
    assert text_version({}) == 1
    assert text_version({"chunking": {"index_text_version": INDEX_TEXT_VERSION}}) == (
        INDEX_TEXT_VERSION
    )
    assert INDEX_TEXT_VERSION >= 2
