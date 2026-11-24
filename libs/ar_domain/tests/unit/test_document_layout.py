"""Layout parsing keeps headings, pages, sheet names and tables.

The samples are files this product writes. Docling reads them when it is
installed. The fallback parser reads the same bytes when it is not.
"""

from __future__ import annotations

from ar_domain.documents.create.render import render
from ar_domain.documents.create.spec import parse
from ar_domain.documents.layout import parse_layout


def _docx() -> bytes:
    return render(
        parse(
            {
                "format": "docx",
                "title": "Policy",
                "sections": [
                    {"heading": "Access", "level": 1, "paragraphs": ["The door stays locked."]},
                    {"heading": "Visitors", "level": 2, "paragraphs": ["Visitors sign the book."]},
                ],
            }
        )
    )


def _xlsx() -> bytes:
    return render(
        parse(
            {
                "format": "xlsx",
                "title": "Regions",
                "sheets": [
                    {"name": "North", "columns": ["City", "Count"], "rows": [["Ada", 2]]},
                ],
            }
        )
    )


def _pptx() -> bytes:
    return render(
        parse(
            {
                "format": "pptx",
                "title": "Roadmap",
                "sections": [
                    {
                        "heading": "Start",
                        "level": 1,
                        "paragraphs": ["The desk opens at eight."],
                        "table": {
                            "caption": "Hours",
                            "columns": ["Day", "Open"],
                            "rows": [["Mon", "8"]],
                        },
                    }
                ],
            }
        )
    )


def test_a_docx_keeps_heading_levels() -> None:
    extracted = parse_layout(_docx(), filename="policy.docx")
    levels = {passage.heading: passage.level for passage in extracted.passages}
    assert levels["Access"] == 1
    assert levels["Visitors"] == 2
    text = "\n".join(passage.text for passage in extracted.passages)
    assert "The door stays locked." in text
    assert "Visitors sign the book." in text
    # Text is filed under the heading it sits beneath, never under a name the parser
    # gives its own groups (a Word file's first section group is called "header-1").
    filed = {passage.text: passage.heading for passage in extracted.passages}
    assert filed["The door stays locked."] == "Access"
    assert filed["Visitors sign the book."] == "Visitors"
    assert not any(passage.heading.startswith("header-") for passage in extracted.passages)


def test_a_workbook_keeps_the_sheet_name() -> None:
    extracted = parse_layout(_xlsx(), filename="regions.xlsx")
    captions = [table.caption for table in extracted.tables]
    assert "North" in captions
    csv_text = "\n".join(table.csv_text for table in extracted.tables)
    assert "City" in csv_text
    assert "Ada" in csv_text
    assert extracted.page_count >= 1


def test_a_deck_keeps_the_table_and_its_page() -> None:
    extracted = parse_layout(_pptx(), filename="roadmap.pptx")
    assert extracted.tables
    table = extracted.tables[0]
    assert table.page >= 1
    assert "Day" in table.csv_text
    assert "Mon" in table.csv_text
    text = "\n".join(passage.text for passage in extracted.passages)
    assert "The desk opens at eight." in text


def test_a_pdf_keeps_its_words() -> None:
    data = render(
        parse(
            {
                "format": "pdf",
                "title": "Notice",
                "sections": [
                    {"heading": "Hours", "paragraphs": ["The desk opens at eight."]},
                ],
            }
        )
    )
    extracted = parse_layout(data, filename="notice.pdf")
    text = "\n".join(passage.text for passage in extracted.passages)
    assert "desk opens at eight" in text
    assert extracted.page_count >= 1
