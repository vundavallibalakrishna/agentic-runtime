"""Layout parsing. Docling is first. ``extract_bytes`` covers what Docling cannot.

The ingest image installs Docling. A process without it, and a format Docling
does not read, uses the fallback parser. Outline level, page and sheet name
come from the layout tree, not from a heading guess.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_common.logging import get_logger
from ar_domain.documents.extract import (
    Extracted,
    ExtractError,
    Passage,
    Table,
    extract_bytes,
    sniff,
)

# HTML stays on the fallback reader: it drops nav, style and script, which the
# layout parser keeps. Markdown and plain text do not need a layout model.
_DOCLING = frozenset({"pdf", "docx", "pptx", "xlsx"})
_CONVERTER: list[Any] = []
_log = get_logger(__name__)


def parse_layout(
    data: bytes,
    *,
    filename: str,
    media_type: str = "",
    ocr: object = None,
    on_page: object = None,
) -> Extracted:
    """One extract. Docling when it can read the file, otherwise ``extract_bytes``."""
    kind = sniff(data, filename, media_type)
    missed = ""
    if kind in _DOCLING:
        parsed, missed = _docling(data, filename, media_type)
        if parsed is not None:
            return parsed
    extracted = extract_bytes(
        data,
        filename=filename,
        media_type=media_type,
        ocr=ocr,  # type: ignore[arg-type]
        on_page=on_page,  # type: ignore[arg-type]
    )
    if missed:
        # The layout parser should have read this file and did not. The fallback reader's
        # text is kept, and the document says which reader it came from and why.
        extracted.metadata["parser"] = "fallback"
        extracted.metadata["parserNote"] = missed
    return extracted


def _docling(data: bytes, filename: str, media_type: str) -> tuple[Extracted | None, str]:
    """The layout parser's reading, or none and the reason it gave none."""
    import importlib.util  # noqa: PLC0415

    try:
        found = importlib.util.find_spec("docling.document_converter")
    except ModuleNotFoundError:
        # Asking for a module inside a package that is not installed raises. A process
        # without the layout parser, such as the tool gateway, is in that case.
        found = None
    if found is None:
        return None, "layout_parser_not_installed"
    name = Path(filename or "upload").name
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / name
            path.write_bytes(data)
            converted = _converter().convert(str(path))
        extracted = _from_docling(converted.document, filename, media_type)
    except Exception as error:  # noqa: BLE001 - a parser failure uses the fallback reader
        # The kind of error and the kind of file, never the file's name or its text.
        _log.warning(
            "layout_parser_failed",
            error=type(error).__name__,
            kind=sniff(data, filename, media_type),
            bytes=len(data),
        )
        return None, f"layout_parser_failed:{type(error).__name__}"
    if not extracted.passages and not extracted.tables:
        return None, "layout_parser_read_nothing"
    return extracted, ""


def _converter() -> Any:
    if _CONVERTER:
        return _CONVERTER[0]
    from docling.document_converter import DocumentConverter  # noqa: PLC0415

    _CONVERTER.append(DocumentConverter())
    return _CONVERTER[0]


def _from_docling(document: object, filename: str, media_type: str) -> Extracted:  # noqa: PLR0915
    passages: list[Passage] = []
    tables: list[Table] = []
    title = Path(filename or "upload").stem or "Document"
    sheet = ""
    # The heading the text being read sits under: the last title or section heading seen.
    section = ""
    section_level = 1
    last_text = ""
    page_max = 0
    ordinal = 0
    items = getattr(document, "iterate_items", None)
    if not callable(items):
        raise ExtractError("unsupported", "The layout parser returned no document.")
    for item, level in items(with_groups=True):
        kind = type(item).__name__
        if _is_group(item):
            # Only a spreadsheet's sheet names its content. The parser's other groups
            # ("header-1", lists, slides) are its own structure, not words in the document.
            if str(getattr(item, "label", "")).rsplit(".", 1)[-1].lower() == "sheet":
                sheet = _label(item)
                section = ""
                section_level = 1
                last_text = ""
            continue
        page = _page(item)
        page_max = max(page_max, page)
        if kind == "TitleItem":
            text = _words(item)
            if text:
                title = text
                section = text
                section_level = 1
            ordinal += 1
            passages.append(
                Passage(
                    anchor=f"p{page}-s{ordinal}",
                    page=page,
                    heading=text or title,
                    level=1,
                    text=text,
                )
            )
            last_text = ""
            continue
        if kind == "SectionHeaderItem":
            text = _words(item)
            heading_level = getattr(item, "level", None)
            resolved = heading_level if isinstance(heading_level, int) else int(level or 1)
            if text:
                section = text
                section_level = max(1, resolved)
            ordinal += 1
            passages.append(
                Passage(
                    anchor=f"p{page}-s{ordinal}",
                    page=page,
                    heading=text,
                    level=max(1, resolved),
                    text=text,
                )
            )
            last_text = ""
            continue
        if kind == "TableItem":
            csv_text = _table_csv(item, document)
            caption = sheet or last_text or "Table"
            ordinal += 1
            anchor = f"t{page}-{ordinal}"
            tables.append(Table(anchor=anchor, page=page, caption=caption[:200], csv_text=csv_text))
            if csv_text.strip():
                passages.append(
                    Passage(
                        anchor=anchor,
                        page=page,
                        heading=caption[:200],
                        level=1,
                        text=csv_text,
                    )
                )
            last_text = ""
            continue
        # Only an item's own words are text. A picture with no caption has none, and the
        # parser's name for its kind ("picture") is not in the document.
        text = _words(item)
        if not text:
            continue
        ordinal += 1
        heading = section or sheet or title
        passages.append(
            Passage(
                anchor=f"p{page}-s{ordinal}",
                page=page,
                heading=heading,
                # Text under a heading carries that heading's level, so a section reads
                # as one level however deep the parser nested its paragraphs.
                level=section_level if section else max(1, int(level or 1)),
                text=text,
            )
        )
        last_text = text
    pages = getattr(document, "pages", None)
    counted = len(pages) if isinstance(pages, dict) and pages else page_max
    return Extracted(
        title=title[:200] or "Document",
        media_type=media_type or "application/octet-stream",
        page_count=max(1, counted or 1),
        passages=passages,
        tables=tables,
        metadata={"parser": "docling"},
    )


def _is_group(item: object) -> bool:
    """A group of the parser's own, including its list and inline groups."""
    return any(cls.__name__ == "GroupItem" for cls in type(item).__mro__)


def _words(item: object) -> str:
    value = getattr(item, "text", None)
    return value.strip() if isinstance(value, str) else ""


def _label(item: object) -> str:
    for name in ("text", "name", "label"):
        value = getattr(item, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _page(item: object) -> int:
    prov = getattr(item, "prov", None)
    if isinstance(prov, list) and prov:
        number = getattr(prov[0], "page_no", None)
        if isinstance(number, int) and number > 0:
            return number
    return 1


def _table_csv(item: object, document: object) -> str:
    export = getattr(item, "export_to_dataframe", None)
    frame = None
    if callable(export):
        try:
            frame = export(doc=document)
        except TypeError:
            frame = export()
        except ValueError, AttributeError:
            frame = None
    if frame is None:
        return ""
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue().strip()
