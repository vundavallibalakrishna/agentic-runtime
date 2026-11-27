"""A document is indexed as passages a search can match and a model can answer from.

A parsed document was cut into a passage a sentence: the parser's names for pictures and
lists were stored as text, every paragraph repeated its heading so each became a section,
and short sections were never joined. Half of a website's passages were under 50
characters. Proof: unit, on files this product writes and a real layout-parser document.
"""

from __future__ import annotations

from docling_core.types.doc.document import DoclingDocument

from ar_domain.documents.create.render import render
from ar_domain.documents.create.spec import parse
from ar_domain.documents.layout import _from_docling
from ar_domain.knowledge.chunker import chunk_markdown
from ar_domain.knowledge.parse import parse_bytes

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _case_study() -> bytes:
    return render(
        parse(
            {
                "format": "docx",
                "title": "Case study",
                "sections": [
                    {
                        "heading": "About the client",
                        "level": 1,
                        "paragraphs": [
                            "The client is a public department.",
                            "It serves nine provinces.",
                        ],
                    },
                    {
                        "heading": "Challenge",
                        "level": 2,
                        "paragraphs": ["Reports took weeks.", "Leaders lacked a clear view."],
                    },
                    {"heading": "Result", "level": 2, "paragraphs": ["Reporting takes a day."]},
                ],
            }
        )
    )


def test_a_heading_is_written_once_for_its_section() -> None:
    markdown = parse_bytes(_case_study(), mime_type=_DOCX, name="case.docx", max_bytes=10**8)
    assert markdown.count("## Challenge") == 1
    assert markdown.count("# About the client") == 1
    assert markdown.count("<!-- page:1 -->") == 1


def test_short_sections_are_one_passage_that_keeps_every_heading() -> None:
    markdown = parse_bytes(_case_study(), mime_type=_DOCX, name="case.docx", max_bytes=10**8)
    [passage] = chunk_markdown(markdown, target_tokens=512)
    for line in (
        "About the client",
        "It serves nine provinces.",
        "Challenge",
        "Leaders lacked a clear view.",
        "Result",
        "Reporting takes a day.",
    ):
        assert line in passage.text
    assert passage.page_from == 1


def test_joined_passages_stay_within_the_target() -> None:
    sections = "\n\n".join(
        f"## Section {number}\n\n" + "A sentence about this part of the work. " * 12
        for number in range(30)
    )
    passages = chunk_markdown(f"# Report\n\n{sections}", target_tokens=200)
    assert len(passages) > 3
    assert all(passage.token_count <= 200 for passage in passages)
    assert [passage.ordinal for passage in passages] == list(range(len(passages)))
    # A passage is filed under the headings its sections share.
    assert all(passage.heading_path[:1] == ["Report"] for passage in passages)


def test_a_section_larger_than_the_target_is_not_joined() -> None:
    long = "## Long\n\n" + "Word " * 900
    passages = chunk_markdown(f"# Doc\n\n## Short\n\nA line.\n\n{long}", target_tokens=128)
    assert any(passage.heading_path == ["Doc", "Long"] for passage in passages)


def test_pictures_and_list_groups_are_not_text() -> None:
    document = DoclingDocument(name="sheet")
    document.add_heading("Overview")
    document.add_picture()
    group = document.add_list_group()
    document.add_list_item("First point", parent=group)
    document.add_list_item("Second point", parent=group)
    texts = [passage.text for passage in _from_docling(document, "sheet.pdf", "").passages]
    assert texts == ["Overview", "First point", "Second point"]
