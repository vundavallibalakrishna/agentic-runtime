"""Parse uploads into Markdown with page anchors.

Docling is used when the ingest extra is installed. The pure parser covers
Markdown, HTML, text, CSV, and the Office zip formats used by the fixtures.
"""

import re
from html.parser import HTMLParser


class ParseError(Exception):
    """Non-retryable parse failure. ``code`` is ``unsupported_format`` or ``too_large``."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def parse_bytes(data: bytes, *, mime_type: str, name: str, max_bytes: int) -> str:
    """Markdown from the one layout parser. Page anchors look like ``<!-- page:N -->``."""
    if len(data) > max_bytes:
        raise ParseError("too_large", "document exceeds AR_INGEST_MAX_BYTES")
    from ar_domain.documents.extract import ExtractError, extract_bytes  # noqa: PLC0415

    try:
        extracted = extract_bytes(data, filename=name, media_type=mime_type)
    except ExtractError as exc:
        if name.lower().endswith(".pdf") or "pdf" in mime_type:
            from ar_domain.documents.extract import pdf_markdown  # noqa: PLC0415

            try:
                return pdf_markdown(data)
            except ExtractError:
                pass
        code = "too_large" if exc.code == "too_many_pages" else "unsupported_format"
        raise ParseError(code, exc.message) from exc
    parts = [
        _as_markdown(passage.page, passage.heading, passage.level, passage.text)
        for passage in extracted.passages
        if passage.text.strip()
    ]
    parts.extend(
        f"<!-- page:{table.page} -->\n\n{table.csv_text}"
        for table in extracted.tables
        if table.csv_text.strip()
    )
    return "\n\n".join(parts)


def _as_markdown(page: int, heading: str, level: int, text: str) -> str:
    """One passage as markdown, with its heading level when the text does not already show it."""
    body = text.strip()
    name = heading.strip()
    marks = "#" * max(1, min(level or 1, 6))
    if name and body.startswith(name):
        rest = body[len(name) :].lstrip()
        body = f"{marks} {name}"
        if rest:
            body = f"{body}\n\n{rest}"
    elif name and not body.startswith("#"):
        body = f"{marks} {name}\n\n{body}"
    return f"<!-- page:{page} -->\n\n{body}"


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


def csv_markdown(raw: str) -> str:
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


def _office(data: bytes, name: str) -> str:
    """Markdown from the library reader. Office files are parsed once."""
    from ar_domain.documents.extract import ExtractError, extract_bytes  # noqa: PLC0415

    try:
        extracted = extract_bytes(data, filename=name)
    except ExtractError as exc:
        code = "too_large" if exc.code == "too_many_pages" else "unsupported_format"
        raise ParseError(code, exc.message) from exc
    parts = [
        _as_markdown(passage.page, passage.heading, passage.level, passage.text)
        for passage in extracted.passages
        if passage.text.strip()
    ]
    parts.extend(
        f"<!-- page:{table.page} -->\n\n{table.csv_text}"
        for table in extracted.tables
        if table.csv_text.strip()
    )
    return "\n\n".join(parts)


def _pdf(data: bytes) -> str:
    """Markdown from the one PDF reader in ``documents.extract``."""
    from ar_domain.documents.extract import ExtractError, pdf_markdown  # noqa: PLC0415

    try:
        return pdf_markdown(data)
    except ExtractError as exc:
        code = "too_large" if exc.code == "too_many_pages" else "unsupported_format"
        raise ParseError(code, exc.message) from exc


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
