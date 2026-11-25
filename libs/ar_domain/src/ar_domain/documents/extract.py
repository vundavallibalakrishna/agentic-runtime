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

from ar_common.offload import blocking
from ar_domain.documents.quality import engine_name

_ATX = re.compile(r"^(#{1,6})\s+(\S.*)$")
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
    char_from: int = 0
    char_to: int = 0


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
    on_page: Callable[[int, int], None] | None = None,
) -> Extracted:
    """Read one file. Encrypted, corrupt and unsupported files raise ExtractError."""
    if not data:
        raise ExtractError("corrupt", "The file is empty.")
    kind = sniff(data, filename, media_type)
    if kind == "pdf":
        return _pdf(data, ocr or _tesseract, on_page)
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
    if kind == "csv":
        return _csv_file(data, filename)
    if kind == "txt":
        return _plain(data, filename)
    if kind == "image":
        return _image(data, filename, ocr or _tesseract)
    if kind == "convert":
        from ar_domain.documents.convert import convert_and_extract  # noqa: PLC0415

        return convert_and_extract(data, filename, media_type)
    raise ExtractError(
        "unsupported",
        "Upload a PDF, DOCX, XLSX, PPTX, TXT, MD, HTML, CSV, image, "
        "or a DOC, XLS, ODT, RTF, EML, MSG or ZIP the ingest image can read.",
    )


def sniff(data: bytes, filename: str, media_type: str) -> str:  # noqa: PLR0911, PLR0912
    """Choose a parser from magic bytes, then the name, then the stated type."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK"):
        # A zip container. Word, Excel and PowerPoint files are known by what is inside;
        # any other container (an OpenDocument file, a plain archive) is known by its name.
        office = _office_kind(data)
        if office:
            return office
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
    if name.endswith(".csv") or stated in {"text/csv", "application/csv"}:
        return "csv"
    if name.endswith(".md") or "markdown" in stated:
        return "md"
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) or stated.startswith("image/"):
        return "image"
    if name.endswith((".doc", ".xls", ".odt", ".ods", ".rtf", ".eml", ".msg", ".zip")):
        return "convert"
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


def _pdf(  # noqa: PLR0912, PLR0915
    data: bytes, ocr: Ocr, on_page: Callable[[int, int], None] | None = None
) -> Extracted:
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
    limit = _page_cap()
    if pages > limit:
        raise ExtractError(
            "too_many_pages",
            f"This PDF has {pages} pages. The limit is {limit}. Split it and upload the parts.",
        )
    passages: list[Passage] = []
    tables: list[Table] = []
    used_ocr = False
    pages_ocr = 0
    scan_without_text = False
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise ExtractError("corrupt", "This PDF could not be read.") from exc
        if text.strip() and not unicode_text(text):
            raise ExtractError(
                "not_unicode",
                "This PDF is not Unicode text. Upload a Unicode PDF, or a scan the "
                "OCR provider can read.",
            )
        if len(text.strip()) < _low_text():
            try:
                read = _ocr_page(page, text, ocr)
            except ExtractError as exc:
                if exc.code != "text_not_extracted":
                    raise
                scan_without_text = True
                read = text
            if read.strip() != text.strip():
                used_ocr = True
                pages_ocr += 1
            text = read
            if text.strip() and not unicode_text(text):
                raise ExtractError(
                    "not_unicode",
                    "OCR did not return Unicode text for this PDF.",
                )
        if text.strip():
            passages.extend(_sections(text, index, len(passages)))
        tables.extend(_pdf_tables(page, index, len(tables)))
        if on_page is not None:
            on_page(index, pages)
    title = ""
    meta = reader.metadata
    if meta is not None and meta.title:
        title = str(meta.title)
    if not passages:
        if scan_without_text:
            raise ExtractError(
                "text_not_extracted",
                "This PDF has no Unicode text and OCR did not extract any.",
            )
        raise ExtractError("no_text", "No text could be read from this PDF.")
    return Extracted(
        title=title or _title_from(passages),
        media_type="application/pdf",
        page_count=pages,
        passages=_chunk_all(passages),
        tables=tables,
        metadata={
            "pages": pages,
            "pagesOcr": pages_ocr,
            "ocrEngine": engine_name(ocr) if used_ocr else "none",
            **({"ocr": True} if used_ocr else {}),
        },
    )


def pdf_markdown(data: bytes) -> str:
    """The one PDF reader. Ingest and the library both call this.

    A file pypdf cannot open falls back to the literal strings in the content
    stream, which is how the simple fixtures are read.
    """
    try:
        extracted = _pdf(data, _tesseract, None)
    except ExtractError as exc:
        if exc.code not in {"corrupt", "no_text", "text_not_extracted"}:
            raise
        return _literal_pdf(data)
    pages = [
        f"<!-- page:{passage.page} -->\n\n{passage.text}"
        for passage in extracted.passages
        if passage.text.strip()
    ]
    if not pages:
        return _literal_pdf(data)
    return "\n\n".join(pages)


def _literal_pdf(data: bytes) -> str:
    raw = data.decode("latin-1", errors="ignore")
    found = re.findall(r"\((?:\\\)|[^)]){1,400}\)\s*Tj", raw)
    if not found:
        raise ExtractError("unsupported_format", "pdf has no extractable text")
    lines = [item[1:-3].replace(r"\(", "(").replace(r"\)", ")") for item in found]
    return "<!-- page:1 -->\n\n" + "\n\n".join(lines)


def _ocr_page(page: object, text: str, ocr: Ocr) -> str:
    parts = [text.strip()]
    failed: ExtractError | None = None
    for blob in _page_images(page):
        try:
            read = ocr(blob).strip()
        except ExtractError as exc:
            failed = exc
            continue
        if read:
            parts.append(read)
    joined = "\n".join(part for part in parts if part)
    if (
        not joined.strip()
        and failed is not None
        and failed.code
        in {
            "text_not_extracted",
            "ocr_unavailable",
            "not_unicode",
        }
    ):
        raise failed
    return joined


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


def unicode_text(text: str) -> bool:
    """True when ``text`` is Unicode prose, not a replacement-character dump."""
    if "\ufffd" in text:
        return False
    if not text:
        return True
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return controls / len(text) <= 0.02


def _csv_file(data: bytes, filename: str) -> Extracted:
    """A CSV file uses the one table reader the knowledge parser already has."""
    from ar_domain.knowledge.parse import csv_markdown  # noqa: PLC0415

    text = csv_markdown(data.decode("utf-8", errors="replace"))
    passages = _chunk_all(_sections(text, 1, 0)) if text.strip() else []
    if not passages:
        raise ExtractError("no_text", "No rows could be read from this CSV.")
    return Extracted(
        title=Path(filename).stem or "Table",
        media_type="text/csv",
        page_count=1,
        passages=passages,
        metadata={"ocrEngine": "none", "pagesOcr": 0},
    )


def _image(data: bytes, filename: str, ocr: Ocr) -> Extracted:
    try:
        text = ocr(data)
    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError("text_not_extracted", "OCR could not read this image.") from exc
    if not text.strip():
        raise ExtractError("text_not_extracted", "No text was extracted from this image.")
    if not unicode_text(text):
        raise ExtractError("not_unicode", "OCR did not return Unicode text for this image.")
    passages = _chunk_all(_sections(text, 1, 0))
    return Extracted(
        title=Path(filename).stem or "Image",
        media_type="image",
        page_count=1,
        passages=passages,
        metadata={"ocr": True, "pagesOcr": 1, "ocrEngine": engine_name(ocr)},
    )


def _tesseract(data: bytes) -> str:
    binary = shutil.which("tesseract")
    if not binary:
        raise ExtractError(
            "text_not_extracted",
            "Tesseract is not in this image, so no text was extracted.",
        )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "page"
        path.write_bytes(data)
        try:
            result = blocking(
                lambda: subprocess.run(  # noqa: S603 — binary is the tesseract on PATH
                    [binary, str(path), "stdout", "-l", "eng"],
                    check=False,
                    capture_output=True,
                    timeout=30,
                    env={"PATH": os.environ.get("PATH", ""), "TMPDIR": tmp},
                )
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
            named = _sheet_names(book)
            sheets = named or [
                (f"Sheet {index}", name)
                for index, name in enumerate(
                    sorted(
                        item for item in book.namelist() if item.startswith("xl/worksheets/sheet")
                    ),
                    start=1,
                )
            ]
            parsed = [(label, _sheet_rows(book.read(path), shared)) for label, path in sheets]
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ExtractError("corrupt", "This spreadsheet could not be read.") from exc
    tables: list[Table] = []
    passages: list[Passage] = []
    sheet_name = ""
    from ar_common.settings import get_settings  # noqa: PLC0415

    preview_rows = int(get_settings().document_table_preview_rows)
    for index, (name, rows) in enumerate(parsed, start=1):
        sheet_name = name
        if not rows:
            continue
        caption = name or f"Sheet {index}"
        tables.append(Table(anchor=f"t{index}", page=index, caption=caption, csv_text=_csv(rows)))
        preview = _csv(rows[:preview_rows])
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


def _sheet_names(book: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Workbook sheet names paired with their worksheet parts."""
    try:
        workbook = _xml(book.read("xl/workbook.xml"))
        rels = _xml(book.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return []
    rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    pkg = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    targets = {
        node.attrib.get("Id", ""): "xl/" + node.attrib.get("Target", "").lstrip("/")
        for node in rels.findall(f"{pkg}Relationship")
    }
    found: list[tuple[str, str]] = []
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for sheet in workbook.findall(f".//{ns}sheet"):
        label = sheet.attrib.get("name") or ""
        path = targets.get(sheet.attrib.get(f"{rel}id", ""), "")
        if label and path:
            found.append((label, path))
    return found


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        payload = book.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = _xml(payload)
    return ["".join(node.itertext()) for node in root.findall(f"{_XLSX}si")]


def _sheet_rows(payload: bytes, shared: list[str]) -> list[list[str]]:
    from ar_common.settings import get_settings  # noqa: PLC0415

    root = _xml(payload)
    rows: list[list[str]] = []
    cap = int(get_settings().document_table_max_rows)
    for index, row in enumerate(root.iter(f"{_XLSX}row")):
        if index >= cap:
            break
        cells: list[str] = []
        for cell in row.findall(f"{_XLSX}c"):
            kind = cell.attrib.get("t")
            if kind == "inlineStr":
                raw = "".join(cell.itertext())
            else:
                value = cell.find(f"{_XLSX}v")
                raw = "" if value is None or value.text is None else value.text
            if kind == "s" and raw.isdigit():
                pointer = int(raw)
                raw = shared[pointer] if pointer < len(shared) else raw
            cells.append(raw[:500])
        if any(cells):
            rows.append(cells)
    return rows


def slide_names(names: list[str]) -> list[str]:
    """The slide parts of a presentation in slide order: slide2 before slide10."""
    slides = [
        name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    ]
    return sorted(slides, key=lambda name: (len(name), name))


def _pptx(data: bytes) -> Extracted:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            slides = slide_names(book.namelist())
            texts = [book.read(name) for name in slides]
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ExtractError("corrupt", "This presentation could not be read.") from exc
    limit = _page_cap()
    if len(slides) > limit:
        raise ExtractError(
            "too_many_pages",
            f"This presentation has {len(slides)} slides. The limit is {limit}.",
        )
    passages: list[Passage] = []
    tables: list[Table] = []
    for index, payload in enumerate(texts, start=1):
        root = _xml(payload)
        for table in root.iter(f"{_A}tbl"):
            rows = _pptx_table(table)
            if rows:
                tables.append(
                    Table(
                        anchor=f"t{len(tables) + 1}",
                        page=index,
                        caption=f"Slide {index}",
                        csv_text=_csv(rows),
                    )
                )
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
        tables=tables,
    )


def _pptx_table(table: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.findall(f"{_A}tr"):
        cells = [
            "".join(node.text or "" for node in cell.iter(f"{_A}t")).strip()
            for cell in row.findall(f"{_A}tc")
        ]
        if any(cells):
            rows.append(cells)
    return rows


# Parts of a web page that are the site around the content, not the content: its menus,
# banners, footers, sidebars, forms and widgets. A page read for a knowledge base keeps
# only what it says, so a search finds the page for its subject, not for its menu.
_HTML_NEVER = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "nav",
        "aside",
        "form",
        "select",
        "button",
        "iframe",
        "dialog",
    }
)
# The site's header is its logo and menu. Its footer is kept: it is where a site gives its
# address, telephone and email, and the menus in it are left out as link lists.
_HTML_FRAME = frozenset({"header"})
_HTML_ROLES = frozenset(
    {"navigation", "banner", "contentinfo", "complementary", "search", "dialog"}
)
_HTML_CONTENT = frozenset({"main", "article"})
_HTML_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
# A list item that is mostly link text, or a link with only a date or a count beside it,
# is a menu entry or a "recent posts" line. A short paragraph that is only a link is a
# button ("Share", "Read more"). Both are left out.
_HTML_LINK_SHARE = 0.6
_HTML_LINK_ASIDE = 30
_HTML_BUTTON = 40
# When the page marks its content (``<main>`` or ``<article>``) and that holds at least
# this much text, only that content and the site's footer are kept.
_HTML_CONTENT_MIN = 200


def _html(data: bytes) -> Extracted:
    from html.parser import HTMLParser  # noqa: PLC0415

    class Collector(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            # (tag, text, inside the page's marked content or its footer)
            self.parts: list[tuple[str, str, bool]] = []
            self.capture = ""
            self.buffer: list[str] = []
            self.linked: list[str] = []
            self.row: list[str] = []
            self.rows: list[list[str]] = []
            self.tables: list[list[list[str]]] = []
            self.open: list[tuple[str, bool]] = []  # (tag, left out)
            self.left_out = 0
            self.content = 0
            self.footer = 0
            # Open links that lead somewhere else. A mailto: or tel: link is the contact
            # detail itself, so its text counts as content.
            self.links: list[bool] = []

        def _leaves_out(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
            found = {name: (value or "") for name, value in attrs}
            if tag in _HTML_NEVER or "hidden" in found:
                return True
            if found.get("aria-hidden", "").lower() == "true":
                return True
            if found.get("role", "").lower() in _HTML_ROLES:
                return True
            # A header inside the content is the article's own (its title, its byline);
            # the site's header sits outside it.
            return tag in _HTML_FRAME and not self.content

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in _HTML_VOID:
                return
            out = self._leaves_out(tag, attrs)
            self.open.append((tag, out))
            self.left_out += out
            self.content += tag in _HTML_CONTENT
            self.footer += tag == "footer"
            if tag == "a":
                href = next((value or "" for name, value in attrs if name == "href"), "")
                self.links.append(not href.lower().startswith(("mailto:", "tel:")))
            if self.left_out:
                return
            if tag in {"h1", "h2", "h3", "p", "li", "td", "th"}:
                self.capture = tag
                self.buffer = []
                self.linked = []
            if tag == "tr":
                self.row = []
            if tag == "table":
                self.rows = []

        def handle_endtag(self, tag: str) -> None:
            if tag in _HTML_VOID or not any(name == tag for name, _ in self.open):
                return
            while self.open:
                name, out = self.open.pop()
                self.left_out -= out
                self.content -= name in _HTML_CONTENT
                self.footer -= name == "footer"
                if name == "a" and self.links:
                    self.links.pop()
                if name == tag:
                    break
            if self.left_out:
                return
            text = "".join(self.buffer).strip()
            if tag == self.capture and text and not self._mostly_links(tag, text):
                kept = bool(self.content or self.footer)
                self.parts.append((tag, re.sub(r"\s+", " ", text), kept))
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
                self.linked = []

        def _mostly_links(self, tag: str, text: str) -> bool:
            linked = len(re.sub(r"\s+", " ", "".join(self.linked)).strip())
            if not linked:
                return False
            if tag == "li":
                rest = len(text) - linked
                return linked >= _HTML_LINK_SHARE * len(text) or rest < _HTML_LINK_ASIDE
            if tag == "p":
                return len(text) <= _HTML_BUTTON and len(text) - linked < 3
            return False

        def handle_data(self, data: str) -> None:
            if self.capture and not self.left_out:
                self.buffer.append(data)
                if any(self.links):
                    self.linked.append(data)

    parser = Collector()
    try:
        parser.feed(data.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise ExtractError("corrupt", "This HTML file could not be read.") from exc
    marked = [(tag, text) for tag, text, inside in parser.parts if inside]
    if sum(len(text) for _, text in marked) >= _HTML_CONTENT_MIN:
        parser_parts = marked
    else:
        parser_parts = [(tag, text) for tag, text, _ in parser.parts]
    passages: list[Passage] = []
    heading = "Document"
    level = 1
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        text = "\n".join(body).strip()
        body = []
        if text and heading and heading not in text:
            text = f"{heading}\n{text}".strip()
        if text:
            passages.extend(_sections(text, 1, len(passages), heading, level))

    for tag, text in parser_parts:
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
    # The document's own first heading names it, even when no text sits directly under it.
    title = ""
    level = 1
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        chunk = "\n".join(body).strip()
        body = []
        if chunk and heading and heading not in chunk:
            chunk = f"{heading}\n{chunk}".strip()
        if chunk:
            passages.extend(_sections(chunk, 1, len(passages), heading, level))

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if match:
            flush()
            heading = match.group(2).strip()
            level = len(match.group(1))
            title = title or heading
            continue
        body.append(line)
    flush()
    if not passages:
        raise ExtractError("no_text", "This file has no readable text.")
    return Extracted(
        title=title or passages[0].heading,
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
            found = _markdown_heading(stripped)
            current = found[1] if found else stripped
            current_level = found[0] if found else current_level
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
    return _markdown_heading(line) is not None


def _markdown_heading(line: str) -> tuple[int, str] | None:
    match = _ATX.match(line.strip())
    if match is None:
        return None
    return len(match.group(1)), match.group(2).strip()


def _page_cap() -> int:
    from ar_common.settings import get_settings  # noqa: PLC0415

    return int(get_settings().document_max_pages)


def _low_text() -> int:
    from ar_common.settings import get_settings  # noqa: PLC0415

    return int(get_settings().document_low_text_chars)


def _pdf_tables(page: object, page_number: int, start: int) -> list[Table]:
    """Tables from the page's layout text. Lines with several wide gaps are rows."""
    try:
        layout = page.extract_text(extraction_mode="layout") or ""  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — a page without layout text still has its passages
        return []
    rows: list[list[str]] = []
    for line in layout.splitlines():
        cells = [cell.strip() for cell in re.split(r"\s{2,}", line.strip()) if cell.strip()]
        if len(cells) >= 2:
            rows.append(cells)
    if len(rows) < 2:
        return []
    return [
        Table(
            anchor=f"t{start + 1}",
            page=page_number,
            caption=f"Page {page_number}",
            csv_text=_csv(rows),
        )
    ]


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
