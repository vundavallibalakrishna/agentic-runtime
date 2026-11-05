"""Extract text, sections and tables from uploaded files.

Office files are zip XML. PDFs use pypdf. Images and scanned pages use the
tesseract binary when it is installed. The bytes are data, never instructions.
"""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_PAGES = 600
_HEADING = re.compile(r"^(?:#{1,6}\s+|(?:\d+|[A-Z])[.)]\s+)(\S.*)$|^(?:[A-Z][A-Z0-9 /,&-]{2,70})$")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_XLSX = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

Ocr = Callable[[bytes], str]


class ExtractError(Exception):
    """A file that cannot be read. ``code`` is the client-facing reason."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class Passage:
    anchor: str
    page: int
    heading: str
    level: int
    text: str


@dataclass
class Table:
    anchor: str
    page: int
    caption: str
    csv_text: str


@dataclass
class Extracted:
    title: str
    media_type: str
    page_count: int
    passages: list[Passage] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


def extract_bytes(  # noqa: PLR0911
    data: bytes,
    *,
    filename: str,
    media_type: str = "",
    ocr: Ocr | None = None,
) -> Extracted:
    """Read one file. Encrypted, corrupt and unsupported files raise ExtractError."""
    if not data:
        raise ExtractError("corrupt", "The file is empty.")
    kind = sniff(data, filename, media_type)
    if kind == "pdf":
        return _pdf(data, ocr or _tesseract)
    if kind == "docx":
        return _docx(data)
    if kind == "xlsx":
        return _xlsx(data)
    if kind == "pptx":
        return _pptx(data)
    if kind == "html":
        return _html(data)
    if kind == "md":
        return _markdown(data, filename)
    if kind == "txt":
        return _plain(data, filename)
    if kind == "image":
        return _image(data, filename, ocr or _tesseract)
    raise ExtractError(
        "unsupported",
        "Upload a PDF, DOCX, XLSX, PPTX, TXT, MD, HTML or image.",
    )


def sniff(data: bytes, filename: str, media_type: str) -> str:  # noqa: PLR0911, PLR0912
    """Choose a parser from magic bytes, then the name, then the stated type."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK"):
        return _office_kind(data)
    if data.startswith(b"\x89PNG") or data.startswith(b"\xff\xd8") or data.startswith(b"GIF"):
        return "image"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image"
    name = filename.lower()
    stated = media_type.lower()
    if name.endswith(".pdf") or "pdf" in stated:
        return "pdf"
    if name.endswith(".docx") or "wordprocessingml" in stated:
        return "docx"
    if name.endswith(".xlsx") or "spreadsheetml" in stated:
        return "xlsx"
    if name.endswith(".pptx") or "presentationml" in stated:
        return "pptx"
    if name.endswith((".html", ".htm")) or "html" in stated:
        return "html"
    if name.endswith(".md") or "markdown" in stated:
        return "md"
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) or stated.startswith("image/"):
        return "image"
    if name.endswith(".txt") or stated.startswith("text/"):
        return "txt"
    sample = data[:200].lstrip()
    if sample.startswith((b"<html", b"<!doctype", b"<HTML")):
        return "html"
    if _looks_text(data):
        return "txt"
    return ""


def _office_kind(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            names = set(book.namelist())
    except zipfile.BadZipFile:
        return ""
    if "word/document.xml" in names:
        return "docx"
    if any(name.startswith("xl/worksheets/") for name in names):
        return "xlsx"
    if any(name.startswith("ppt/slides/slide") for name in names):
        return "pptx"
    return ""


def _looks_text(data: bytes) -> bool:
    sample = data[:4000]
    if not sample:
        return False
    if b"\x00" in sample:
        return False
    text = sample.decode("utf-8", errors="ignore")
    return (
        bool(text) and sum(char.isprintable() or char.isspace() for char in text) / len(text) > 0.9
    )


def _pdf(data: bytes, ocr: Ocr) -> Extracted:
    from pypdf import PdfReader  # noqa: PLC0415
    from pypdf.errors import PdfReadError  # noqa: PLC0415

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError, OSError) as exc:
        raise ExtractError("corrupt", "This PDF could not be read.") from exc
    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception as exc:
            raise ExtractError(
                "encrypted", "This PDF is encrypted. Upload an unlocked copy."
            ) from exc
        if unlocked == 0:
            raise ExtractError("encrypted", "This PDF is encrypted. Upload an unlocked copy.")
    pages = len(reader.pages)
    if pages > MAX_PAGES:
        raise ExtractError(
            "too_many_pages",
            f"This PDF has {pages} pages. The limit is {MAX_PAGES}. Split it and upload the parts.",
        )
    passages: list[Passage] = []
    used_ocr = False
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise ExtractError("corrupt", "This PDF could not be read.") from exc
        if len(text.strip()) < 20:
            read = _ocr_page(page, text, ocr)
            if read.strip() != text.strip():
                used_ocr = True
            text = read
        passages.extend(_sections(text, index, len(passages)))
    title = ""
    meta = reader.metadata
    if meta is not None and meta.title:
        title = str(meta.title)
    if not passages:
        raise ExtractError("no_text", "No text could be read from this PDF.")
    return Extracted(
        title=title or _title_from(passages),
        media_type="application/pdf",
        page_count=pages,
        passages=_chunk_all(passages),
        metadata={"pages": pages, **({"ocr": True} if used_ocr else {})},
    )


def _ocr_page(page: object, text: str, ocr: Ocr) -> str:
    parts = [text.strip()]
    for blob in _page_images(page):
        try:
            parts.append(ocr(blob).strip())
        except ExtractError:
            continue
    return "\n".join(part for part in parts if part)


def _page_images(page: object) -> list[bytes]:
    """Image bytes from the page. Raw streams do not need Pillow."""
    blobs = _xobject_images(page)
    if blobs:
        return blobs
    return _pillow_images(page)


def _pdf_object(value: object) -> object:
    getter = getattr(value, "get_object", None)
    if callable(getter):
        return getter()
    return value


def _xobject_images(page: object) -> list[bytes]:
    getter = getattr(page, "get", None)
    if not callable(getter):
        return []
    resources = _pdf_object(getter("/Resources"))
    resource_get = getattr(resources, "get", None)
    if not callable(resource_get):
        return []
    xobjects = _pdf_object(resource_get("/XObject"))
    values = getattr(xobjects, "values", None)
    if not callable(values):
        return []
    blobs: list[bytes] = []
    for item in values():
        stream = _pdf_object(item)
        stream_get = getattr(stream, "get", None)
        data_fn = getattr(stream, "get_data", None)
        if not callable(stream_get) or not callable(data_fn):
            continue
        if str(stream_get("/Subtype") or "") != "/Image":
            continue
        data: object = None
        try:
            data = data_fn()
        except Exception:  # noqa: BLE001 — one bad image must not drop the page
            data = None
        if isinstance(data, bytes) and data:
            blobs.append(data)
    return blobs


def _pillow_images(page: object) -> list[bytes]:
    try:
        images = getattr(page, "images", None)
        if not images:
            return []
        blobs: list[bytes] = []
        for image in images:
            blob = getattr(image, "data", None)
            if isinstance(blob, bytes) and blob:
                blobs.append(blob)
    except ImportError:
        return []
    else:
        return blobs


def _image(data: bytes, filename: str, ocr: Ocr) -> Extracted:
    try:
        text = ocr(data)
    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError("ocr_unavailable", "OCR could not read this image.") from exc
    if not text.strip():
        raise ExtractError("no_text", "OCR did not find text in this image.")
    passages = _chunk_all(_sections(text, 1, 0))
    return Extracted(
        title=Path(filename).stem or "Image",
        media_type="image",
        page_count=1,
        passages=passages,
        metadata={"ocr": True},
    )


def _tesseract(data: bytes) -> str:
    binary = shutil.which("tesseract")
    if not binary:
        raise ExtractError(
            "ocr_unavailable",
            "OCR is not installed on this runtime, so this image could not be read.",
        )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "page"
        path.write_bytes(data)
        try:
            result = subprocess.run(  # noqa: S603 — binary is the tesseract on PATH
                [binary, str(path), "stdout", "-l", "eng"],
                check=False,
                capture_output=True,
                timeout=30,
                env={"PATH": os.environ.get("PATH", ""), "TMPDIR": tmp},
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractError("ocr_unavailable", "OCR took too long on this image.") from exc
    if result.returncode != 0:
        raise ExtractError("ocr_unavailable", "OCR could not read this image.")
    return result.stdout.decode("utf-8", errors="replace")


def _docx(data: bytes) -> Extracted:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            xml = book.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ExtractError("corrupt", "This document could not be read.") from exc
    root = _xml(xml)
    body = root.find(f"{_W}body")
    nodes = list(body) if body is not None else list(root)
    passages: list[Passage] = []
    tables: list[Table] = []
    buffer: list[str] = []
    heading = "Document"
    level = 1

    def flush() -> None:
        nonlocal buffer
        text = "\n".join(line for line in buffer if line).strip()
        buffer = []
        if text:
            passages.extend(_sections(f"{heading}\n{text}", 1, len(passages), heading, level))

    for node in nodes:
        if node.tag == f"{_W}p":
            style, line = _docx_paragraph(node)
            if style.startswith("Heading"):
                flush()
                heading = line or heading
                level = _heading_level(style)
                continue
            if line:
                buffer.append(line)
        elif node.tag == f"{_W}tbl":
            flush()
            rows = _docx_table(node)
            if rows:
                tables.append(
                    Table(
                        anchor=f"t{len(tables) + 1}",
                        page=1,
                        caption=heading,
                        csv_text=_csv(rows),
                    )
                )
    flush()
    if not passages and not tables:
        raise ExtractError("no_text", "This document has no readable text.")
    return Extracted(
        title=_title_from(passages) if passages else "Document",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        page_count=1,
        passages=_chunk_all(passages),
        tables=tables,
    )


def _docx_paragraph(node: ET.Element) -> tuple[str, str]:
    style = ""
    props = node.find(f"{_W}pPr")
    if props is not None:
        named = props.find(f"{_W}pStyle")
        if named is not None:
            style = named.attrib.get(f"{_W}val", "")
    line = "".join(item.text or "" for item in node.iter(f"{_W}t")).strip()
    return style, line


def _docx_table(node: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in node.findall(f"{_W}tr"):
        cells = [
            "".join(item.text or "" for item in cell.iter(f"{_W}t")).strip()
            for cell in row.findall(f"{_W}tc")
        ]
        if any(cells):
            rows.append(cells)
    return rows


def _xlsx(data: bytes) -> Extracted:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            shared = _shared_strings(book)
            sheets = sorted(
                name for name in book.namelist() if name.startswith("xl/worksheets/sheet")
            )
            parsed = [(name, _sheet_rows(book.read(name), shared)) for name in sheets]
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ExtractError("corrupt", "This spreadsheet could not be read.") from exc
    tables: list[Table] = []
    passages: list[Passage] = []
    sheet_name = ""
    for index, (name, rows) in enumerate(parsed, start=1):
        sheet_name = name
        if not rows:
            continue
        caption = f"Sheet {index}"
        tables.append(Table(anchor=f"t{index}", page=index, caption=caption, csv_text=_csv(rows)))
        preview = _csv(rows[:8])
        passages.append(
            Passage(
                anchor=f"p{index}-s0",
                page=index,
                heading=caption,
                level=1,
                text=f"{caption}\n{preview}",
            )
        )
    if not tables:
        raise ExtractError("no_text", "This spreadsheet has no rows.")
    return Extracted(
        title="Spreadsheet",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        page_count=max(1, len(tables)),
        passages=passages,
        tables=tables,
        metadata={"sheet": sheet_name},
    )


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        payload = book.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = _xml(payload)
    return ["".join(node.itertext()) for node in root.findall(f"{_XLSX}si")]


def _sheet_rows(payload: bytes, shared: list[str]) -> list[list[str]]:
    root = _xml(payload)
    rows: list[list[str]] = []
    for index, row in enumerate(root.iter(f"{_XLSX}row")):
        if index >= 2000:
            break
        cells: list[str] = []
        for cell in row.findall(f"{_XLSX}c"):
            kind = cell.attrib.get("t")
            value = cell.find(f"{_XLSX}v")
            raw = "" if value is None or value.text is None else value.text
            if kind == "s" and raw.isdigit():
                pointer = int(raw)
                raw = shared[pointer] if pointer < len(shared) else raw
            cells.append(raw[:500])
        if any(cells):
            rows.append(cells)
    return rows


def _pptx(data: bytes) -> Extracted:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            slides = sorted(
                name
                for name in book.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            texts = [book.read(name) for name in slides]
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ExtractError("corrupt", "This presentation could not be read.") from exc
    if len(slides) > MAX_PAGES:
        raise ExtractError(
            "too_many_pages",
            f"This presentation has {len(slides)} slides. The limit is {MAX_PAGES}.",
        )
    passages: list[Passage] = []
    for index, payload in enumerate(texts, start=1):
        root = _xml(payload)
        lines = [
            node.text.strip() for node in root.iter(f"{_A}t") if node.text and node.text.strip()
        ]
        if not lines:
            continue
        heading = lines[0][:120]
        body = "\n".join(lines)
        passages.extend(_sections(body, index, len(passages), heading, 1))
    if not passages:
        raise ExtractError("no_text", "This presentation has no readable text.")
    return Extracted(
        title=passages[0].heading,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        page_count=len(slides),
        passages=_chunk_all(passages),
    )


def _html(data: bytes) -> Extracted:
    from html.parser import HTMLParser  # noqa: PLC0415

    class Collector(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[tuple[str, str]] = []
            self.capture = ""
            self.buffer: list[str] = []
            self.row: list[str] = []
            self.rows: list[list[str]] = []
            self.tables: list[list[list[str]]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            del attrs
            if tag in {"h1", "h2", "h3", "p", "li", "td", "th"}:
                self.capture = tag
                self.buffer = []
            if tag == "tr":
                self.row = []
            if tag == "table":
                self.rows = []

        def handle_endtag(self, tag: str) -> None:
            text = "".join(self.buffer).strip()
            if tag == self.capture and text:
                self.parts.append((tag, re.sub(r"\s+", " ", text)))
            if tag in {"td", "th"} and text:
                self.row.append(re.sub(r"\s+", " ", text))
            if tag == "tr" and self.row:
                self.rows.append(self.row)
                self.row = []
            if tag == "table" and self.rows:
                self.tables.append(self.rows)
                self.rows = []
            if tag == self.capture:
                self.capture = ""
                self.buffer = []

        def handle_data(self, data: str) -> None:
            if self.capture:
                self.buffer.append(data)

    parser = Collector()
    try:
        parser.feed(data.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise ExtractError("corrupt", "This HTML file could not be read.") from exc
    passages: list[Passage] = []
    heading = "Document"
    level = 1
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        text = "\n".join(body).strip()
        body = []
        if text:
            passages.extend(_sections(text, 1, len(passages), heading, level))

    for tag, text in parser.parts:
        if tag in {"h1", "h2", "h3"}:
            flush()
            heading = text
            level = int(tag[1])
        else:
            body.append(text)
    flush()
    tables = [
        Table(anchor=f"t{index}", page=1, caption=heading, csv_text=_csv(rows))
        for index, rows in enumerate(parser.tables, start=1)
        if rows
    ]
    if not passages and not tables:
        raise ExtractError("no_text", "This HTML file has no readable text.")
    return Extracted(
        title=_title_from(passages) if passages else "Document",
        media_type="text/html",
        page_count=1,
        passages=_chunk_all(passages),
        tables=tables,
    )


def _markdown(data: bytes, filename: str) -> Extracted:
    text = data.decode("utf-8", errors="replace")
    passages: list[Passage] = []
    heading = Path(filename).stem or "Document"
    level = 1
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        chunk = "\n".join(body).strip()
        body = []
        if chunk:
            passages.extend(_sections(chunk, 1, len(passages), heading, level))

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if match:
            flush()
            heading = match.group(2).strip()
            level = len(match.group(1))
            continue
        body.append(line)
    flush()
    if not passages:
        raise ExtractError("no_text", "This file has no readable text.")
    return Extracted(
        title=passages[0].heading,
        media_type="text/markdown",
        page_count=1,
        passages=_chunk_all(passages),
    )


def _plain(data: bytes, filename: str) -> Extracted:
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        raise ExtractError("no_text", "This file has no readable text.")
    title = Path(filename).stem or "Document"
    return Extracted(
        title=title,
        media_type="text/plain",
        page_count=1,
        passages=_chunk_all(_sections(text, 1, 0, title, 1)),
    )


def _sections(
    text: str,
    page: int,
    start: int,
    heading: str = "",
    level: int = 1,
) -> list[Passage]:
    blocks: list[tuple[str, int, list[str]]] = []
    current = heading or f"Page {page}"
    current_level = level if heading else 1
    buffer: list[str] = []
    pending_heading = False
    for line in text.splitlines():
        stripped = line.strip()
        if _is_heading(stripped) and buffer:
            blocks.append((current, current_level, buffer))
            current = stripped.lstrip("#").strip()
            current_level = 2
            buffer = []
            pending_heading = True
            continue
        if stripped:
            buffer.append(stripped)
            pending_heading = False
    if buffer:
        blocks.append((current, current_level, buffer))
    elif pending_heading and current:
        blocks.append((current, current_level, [current]))
    if not blocks and text.strip():
        blocks.append((current, current_level, [text.strip()]))
    passages: list[Passage] = []
    for offset, (name, depth, lines) in enumerate(blocks):
        body = "\n".join(lines).strip()
        if not body:
            continue
        passages.append(
            Passage(
                anchor=f"p{page}-s{start + offset}",
                page=page,
                heading=name[:160],
                level=depth,
                text=body,
            )
        )
    return passages


def _is_heading(line: str) -> bool:
    if not line or len(line) > 80 or line.endswith("."):
        return False
    return _HEADING.match(line) is not None and len(line.split()) <= 12


def _chunk_all(passages: list[Passage]) -> list[Passage]:
    from ar_domain.documents.chunk import split_passage  # noqa: PLC0415

    return split_passage(passages)


def _heading_level(style: str) -> int:
    digits = re.findall(r"\d+", style)
    if not digits:
        return 1
    return max(1, min(int(digits[0]), 6))


def _title_from(passages: list[Passage]) -> str:
    if not passages:
        return "Document"
    return passages[0].heading or "Document"


def _csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def _xml(payload: bytes) -> ET.Element:
    try:
        return ET.fromstring(payload)  # noqa: S314 — office XML from the uploaded zip
    except ET.ParseError as exc:
        raise ExtractError("corrupt", "This file could not be read.") from exc
