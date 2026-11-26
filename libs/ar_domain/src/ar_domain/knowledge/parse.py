"""Parse uploads into Markdown with page anchors.

Docling is the layout parser. ``extract_bytes`` covers a format Docling cannot
read, and a process that does not have Docling installed.
"""


class ParseError(Exception):
    """Non-retryable parse failure. ``code`` is ``unsupported_format`` or ``too_large``."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def parse_bytes(data: bytes, *, mime_type: str, name: str, max_bytes: int) -> str:
    """Markdown from the one layout parser. Page anchors look like ``<!-- page:N -->``."""
    if len(data) > max_bytes:
        raise ParseError("too_large", "document exceeds AR_INGEST_MAX_BYTES")
    from ar_domain.documents.extract import ExtractError  # noqa: PLC0415
    from ar_domain.documents.layout import parse_layout  # noqa: PLC0415

    try:
        extracted = parse_layout(data, filename=name, media_type=mime_type)
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
