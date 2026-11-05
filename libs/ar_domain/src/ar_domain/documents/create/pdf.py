"""PDF 1.4 writer. Text uses WinAnsi (cp1252) and the standard Helvetica fonts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.documents.create.spec import MAX_PAGES, Cell, CreateError

if TYPE_CHECKING:
    from ar_domain.documents.create.spec import DocumentSpec, Table

_PAGE_W = 595.28
_PAGE_H = 841.89
_MARGIN = 56.0
_BOTTOM = 52.0
_CONTENT_W = _PAGE_W - (_MARGIN * 2)


def render_pdf(spec: DocumentSpec) -> bytes:
    cursor = _Cursor(spec.title, running_header=spec.theme.show_header)
    cursor.line(spec.title, "F1", spec.theme.pdf_title, spec.theme.accent, after=6)
    if spec.subtitle:
        cursor.line(spec.subtitle, "F3", spec.theme.pdf_body, "5B6775", after=2)
    cursor.line(spec.author, "F2", 9, "888888", after=12)
    for section in spec.sections:
        cursor.gap(6)
        size = spec.theme.pdf_heading if section.level == 1 else spec.theme.pdf_heading - 1
        cursor.line(section.heading, "F1", size, spec.theme.accent, after=4)
        for paragraph in section.paragraphs:
            cursor.line(paragraph, "F2", spec.theme.pdf_body, "222222", after=3)
        for bullet in section.bullets:
            cursor.line(f"- {bullet}", "F2", spec.theme.pdf_body, "222222", indent=12, after=2)
        if section.table is not None:
            cursor.table(section.table, spec.theme.accent)
    return _assemble(cursor.finish(), spec)


class _Cursor:
    def __init__(self, title: str, *, running_header: bool) -> None:
        self.title = title
        self.running_header = running_header
        self.pages: list[list[bytes]] = [[]]
        self.y = _PAGE_H - _MARGIN

    def gap(self, amount: float) -> None:
        self.y -= amount

    def line(
        self,
        text: str,
        font: str,
        size: float,
        color: str,
        *,
        indent: float = 0,
        after: float = 2,
    ) -> None:
        if not text:
            return
        width = _CONTENT_W - indent
        for row in _wrap(text, size, width):
            self._ensure(size * 1.4)
            self.pages[-1].append(_text(font, size, color, (_MARGIN + indent, self.y), row))
            self.y -= size * 1.35
        self.y -= after

    def table(self, table: Table, accent: str) -> None:
        if table.caption:
            self.line(table.caption, "F3", 10, "5B6775", after=3)
        widths = _widths(table)
        self._table_header(table, widths, accent)
        for row in table.rows:
            height = _row_height(row, widths, 10)
            if self.y - height < _BOTTOM:
                self._new_page()
                self._table_header(table, widths, accent)
            self._table_row(row, widths, height)

    def finish(self) -> list[bytes]:
        if len(self.pages) > MAX_PAGES:
            raise CreateError(f"The document is over {MAX_PAGES} pages. Split it.")
        streams: list[bytes] = []
        total = len(self.pages)
        for index, ops in enumerate(self.pages, start=1):
            footer = _text("F2", 9, "666666", (_PAGE_W - 80, 32), f"{index} / {total}")
            rule = b"0.85 0.87 0.90 RG 56 46 m 539.28 46 l S"
            streams.append(b"\n".join([*ops, rule, footer]))
        return streams

    def _table_header(self, table: Table, widths: list[float], accent: str) -> None:
        height = 18.0
        self._ensure(height + 4)
        top = self.y
        bottom = top - height
        x = _MARGIN
        self.pages[-1].append(_rect(_rgb(accent), x, bottom, sum(widths), height))
        for index, name in enumerate(table.columns):
            self.pages[-1].append(_text("F1", 9, "FFFFFF", (x + 4, bottom + 5), name))
            x += widths[index]
        self.y = bottom - 2

    def _table_row(self, row: tuple[Cell, ...], widths: list[float], height: float) -> None:
        top = self.y
        bottom = top - height
        x = _MARGIN
        self.pages[-1].append(_rect("0.96 0.97 0.98", x, bottom, sum(widths), height))
        self.pages[-1].append(
            f"0.82 0.84 0.88 RG {x:.2f} {bottom:.2f} {sum(widths):.2f} {height:.2f} re S".encode()
        )
        for index, width in enumerate(widths):
            cell = row[index] if index < len(row) else Cell("", None)
            lines = _wrap(cell.text, 10, width - 8) or [""]
            text_y = top - 12
            for line in lines[:4]:
                drawn = line
                if cell.number is not None and line == lines[0]:
                    text_width = len(line) * 10 * 0.5
                    origin = x + width - 4 - text_width
                else:
                    origin = x + 4
                self.pages[-1].append(_text("F2", 9, "222222", (origin, text_y), drawn))
                text_y -= 11
            x += width
        self.y = bottom - 1

    def _ensure(self, height: float) -> None:
        if self.y - height >= _BOTTOM:
            return
        self._new_page()

    def _new_page(self) -> None:
        if len(self.pages) >= MAX_PAGES:
            raise CreateError(f"The document is over {MAX_PAGES} pages. Split it.")
        self.pages.append([])
        self.y = _PAGE_H - _MARGIN
        if self.running_header and self.title:
            self.pages[-1].append(_text("F2", 9, "5B6775", (_MARGIN, self.y), self.title))
            self.y -= 16


def _assemble(pages: list[bytes], spec: DocumentSpec) -> bytes:
    count = len(pages)
    page_ids = [6 + (index * 2) for index in range(count)]
    content_ids = [page_id + 1 for page_id in page_ids]
    info_id = 6 + (count * 2)
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {count} /Kids [{kids}] >>".encode(),
        _font("Helvetica-Bold"),
        _font("Helvetica"),
        _font("Helvetica-Oblique"),
    ]
    resources = b"<< /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >>"
    page_objects: list[bytes] = []
    for index, _page_id in enumerate(page_ids):
        content_id = content_ids[index]
        page_objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources "
            + resources
            + f" /Contents {content_id} 0 R >>".encode()
        )
        page_objects.append(_stream(pages[index]))
    objects.extend(page_objects)
    objects.append(
        b"<< /Title "
        + _literal(spec.title)
        + b" /Author "
        + _literal(spec.author)
        + b" /Subject "
        + _literal(spec.subtitle)
        + b" /Creator (Agentic Runtime) /Producer (Agentic Runtime) >>"
    )
    if len(objects) != info_id:
        raise CreateError("The PDF could not be assembled.")
    return _pdf(objects, info_id)


def _font(name: str) -> bytes:
    return (
        f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>".encode()
    )


def _stream(data: bytes) -> bytes:
    return b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream"


def _pdf(objects: list[bytes], info_id: int) -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode())
        out.extend(body)
        if not body.endswith(b"\n"):
            out.extend(b"\n")
        out.extend(b"endobj\n")
    xref_at = len(out)
    size = len(objects) + 1
    out.extend(f"xref\n0 {size}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {size} /Root 1 0 R /Info {info_id} 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(out)


def _text(font: str, size: float, color: str, origin: tuple[float, float], text: str) -> bytes:
    shown = text if len(text) <= 180 else text[:177] + "..."
    x, y = origin
    return (
        f"BT /{font} {size:.2f} Tf {_rgb(color)} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ".encode()
        + _literal(shown)
        + b" Tj ET"
    )


def _rect(color: str, x: float, y: float, width: float, height: float) -> bytes:
    return f"{color} rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f".encode()


def _literal(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    out = bytearray(b"(")
    for byte in raw:
        if byte in {0x5C, 0x28, 0x29}:
            out.extend(b"\\" + bytes((byte,)))
        elif byte < 32:
            out.extend(b" ")
        else:
            out.append(byte)
    out.append(0x29)
    return bytes(out)


def _rgb(color: str) -> str:
    if len(color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in color):
        return "0 0 0"
    value = int(color, 16)
    red = ((value >> 16) & 255) / 255
    green = ((value >> 8) & 255) / 255
    blue = (value & 255) / 255
    return f"{red:.3f} {green:.3f} {blue:.3f}"


def _wrap(text: str, size: float, width: float) -> list[str]:
    max_chars = max(8, int(width / (size * 0.52)))
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if len(trial) <= max_chars:
            current = trial
        else:
            lines.extend(_hard(current, max_chars))
            current = word
    lines.extend(_hard(current, max_chars))
    return lines


def _hard(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _widths(table: Table) -> list[float]:
    weights: list[int] = []
    for index, name in enumerate(table.columns):
        longest = len(name)
        for row in table.rows:
            if index < len(row):
                longest = max(longest, min(len(row[index].text), 32))
        weights.append(max(longest, 4))
    total = sum(weights) or 1
    floor = min(48.0, _CONTENT_W / max(1, len(weights)))
    raw = [max(floor, _CONTENT_W * (weight / total)) for weight in weights]
    scale = _CONTENT_W / sum(raw)
    return [item * scale for item in raw]


def _row_height(row: tuple[Cell, ...], widths: list[float], size: float) -> float:
    lines = 1
    for index, width in enumerate(widths):
        cell = row[index] if index < len(row) else Cell("", None)
        lines = max(lines, min(4, len(_wrap(cell.text, size, width - 8)) or 1))
    return 8 + (lines * 11)
