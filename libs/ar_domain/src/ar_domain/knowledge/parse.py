"""Parse uploads into Markdown with page anchors.

Docling is used when the ingest extra is installed. The pure parser covers
Markdown, HTML, text, CSV, and the Office zip formats used by the fixtures.
"""

import io
import re
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

_XML = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PPT = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_XLS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class ParseError(Exception):
    """Non-retryable parse failure. ``code`` is ``unsupported_format`` or ``too_large``."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def parse_bytes(data: bytes, *, mime_type: str, name: str, max_bytes: int) -> str:  # noqa: PLR0911
    """Return Markdown. Page anchors look like ``<!-- page:N -->``."""
    if len(data) > max_bytes:
        raise ParseError("too_large", "document exceeds AR_INGEST_MAX_BYTES")
    kind = _kind(mime_type, name)
    if kind == "markdown":
        return data.decode("utf-8", errors="replace")
    if kind == "html":
        return _html(data.decode("utf-8", errors="replace"))
    if kind == "text":
        return data.decode("utf-8", errors="replace")
    if kind == "csv":
        return _csv(data.decode("utf-8", errors="replace"))
    if kind == "docx":
        return _docx(data)
    if kind == "pptx":
        return _pptx(data)
    if kind == "xlsx":
        return _xlsx(data)
    if kind == "pdf":
        return _pdf(data)
    docling = _docling(data, name)
    if docling is not None:
        return docling
    raise ParseError("unsupported_format", f"unsupported format {kind or mime_type}")


def _kind(mime_type: str, name: str) -> str:  # noqa: PLR0911
    lowered = name.lower()
    if lowered.endswith((".md", ".markdown")) or "markdown" in mime_type:
        return "markdown"
    if lowered.endswith((".html", ".htm")) or "html" in mime_type:
        return "html"
    if lowered.endswith(".csv") or mime_type == "text/csv":
        return "csv"
    if lowered.endswith(".docx"):
        return "docx"
    if lowered.endswith(".pptx"):
        return "pptx"
    if lowered.endswith(".xlsx"):
        return "xlsx"
    if lowered.endswith(".pdf") or mime_type == "application/pdf":
        return "pdf"
    if mime_type.startswith("text/") or lowered.endswith(".txt"):
        return "text"
    return ""


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag in {"script", "style", "nav", "footer"}:
            self._skip += 1
        if tag in {"p", "h1", "h2", "h3", "li", "br", "tr"}:
            self.parts.append("\n")
        if tag in {"h1", "h2", "h3"}:
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")


def _html(raw: str) -> str:
    parser = _HTMLText()
    parser.feed(raw)
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.parts)).strip()


def _csv(raw: str) -> str:
    rows = [line.split(",") for line in raw.splitlines() if line.strip()]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    lines = []
    for index, row in enumerate(rows):
        padded = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(cell.strip() for cell in padded) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in padded) + " |")
    return "\n".join(lines)


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            xml = book.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ParseError("unsupported_format", "docx is not readable") from exc
    root = ET.fromstring(xml)  # noqa: S314 - the bytes are the uploaded document
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_XML}p"):
        texts = [node.text or "" for node in paragraph.iter(f"{_XML}t")]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def _pptx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            slides = sorted(name for name in book.namelist() if name.startswith("ppt/slides/slide"))
            pages = []
            for index, name in enumerate(slides, start=1):
                root = ET.fromstring(book.read(name))  # noqa: S314
                texts = [node.text or "" for node in root.iter(f"{_PPT}t")]
                body = " ".join(text.strip() for text in texts if text.strip())
                pages.append(f"<!-- page:{index} -->\n\n{body}")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ParseError("unsupported_format", "pptx is not readable") from exc
    return "\n\n".join(pages)


def _xlsx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in book.namelist():
                root = ET.fromstring(book.read("xl/sharedStrings.xml"))  # noqa: S314
                shared = [
                    "".join(node.text or "" for node in item.iter(f"{_XLS}t"))
                    for item in root.iter(f"{_XLS}si")
                ]
            sheets = sorted(name for name in book.namelist() if name.startswith("xl/worksheets/"))
            pages = []
            for index, name in enumerate(sheets, start=1):
                root = ET.fromstring(book.read(name))  # noqa: S314
                rows: list[str] = []
                cells = 0
                for row in root.iter(f"{_XLS}row"):
                    values: list[str] = []
                    for cell in row.findall(f"{_XLS}c"):
                        cells += 1
                        if cells > 50_000:
                            break
                        values.append(_cell(cell, shared))
                    if values:
                        rows.append("| " + " | ".join(values) + " |")
                pages.append(f"<!-- page:{index} -->\n\n" + "\n".join(rows))
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ParseError("unsupported_format", "xlsx is not readable") from exc
    return "\n\n".join(pages)


def _cell(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    value = cell.find(f"{_XLS}v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        index = int(value.text)
        return shared[index] if index < len(shared) else ""
    return value.text


def _pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # noqa: PLC0415
    except ModuleNotFoundError:
        return _pdf_text(data)
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - a broken PDF falls back to literal strings
        return _pdf_text(data)
    if len(reader.pages) > 2000:
        raise ParseError("too_large", "document exceeds 2000 pages")
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append(f"<!-- page:{index} -->\n\n{page.extract_text() or ''}")
    return "\n\n".join(pages)


def _pdf_text(data: bytes) -> str:
    """Read literal strings from a simple PDF when pypdf is not installed."""
    raw = data.decode("latin-1", errors="ignore")
    found = re.findall(r"\((?:\\\)|[^)]){1,400}\)\s*Tj", raw)
    if not found:
        raise ParseError("unsupported_format", "pdf has no extractable text")
    lines = [item[1:-3].replace(r"\(", "(").replace(r"\)", ")") for item in found]
    return "<!-- page:1 -->\n\n" + "\n\n".join(lines)


def _docling(data: bytes, name: str) -> str | None:
    try:
        from docling.document_converter import DocumentConverter  # noqa: PLC0415
    except ModuleNotFoundError:
        return None
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / name
        path.write_bytes(data)
        converted = DocumentConverter().convert(str(path))
    return str(converted.document.export_to_markdown())
