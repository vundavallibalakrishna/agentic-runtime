"""Structured input for a created office file. Public names are camelCase."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from pathlib import Path

from ar_common.sandboxkit import sanitise_name

MAX_SECTIONS = 40
MAX_SHEETS = 12
MAX_ROWS = 500
MAX_COLUMNS = 32
MAX_PARAGRAPHS = 40
MAX_BULLETS = 40
MAX_TEXT = 4_000
MAX_TITLE = 200
MAX_FILE_BYTES = 5_242_880
MAX_PAGES = 30

FORMATS = frozenset({"docx", "pdf", "xlsx"})
TEMPLATES = frozenset({"report", "brief", "sheet"})
MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_SLUG = re.compile(r"[^a-z0-9]+")


class CreateError(ValueError):
    """The payload cannot be rendered. The message is safe to show."""


@dataclass(frozen=True)
class Cell:
    text: str
    number: float | None


@dataclass(frozen=True)
class Table:
    caption: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


@dataclass(frozen=True)
class Section:
    heading: str
    level: int
    paragraphs: tuple[str, ...]
    bullets: tuple[str, ...]
    table: Table | None


@dataclass(frozen=True)
class Sheet:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


@dataclass(frozen=True)
class Theme:
    name: str
    accent: str
    title_half_points: int
    heading_half_points: int
    show_header: bool
    pdf_title: float
    pdf_heading: float
    pdf_body: float


@dataclass(frozen=True)
class DocumentSpec:
    format: str
    title: str
    subtitle: str
    author: str
    template: str
    filename: str
    sections: tuple[Section, ...]
    sheets: tuple[Sheet, ...]
    theme: Theme


def theme_for(name: str) -> Theme:
    """Report is the default. Brief is tighter and has no running header."""
    if name == "brief":
        return Theme("brief", "1F4E79", 32, 26, False, 16, 13, 11)
    return Theme(name or "report", "1F4E79", 44, 32, True, 22, 14, 11)


def parse(arguments: dict[str, object]) -> DocumentSpec:
    """Read one create call. Missing optional fields use the template default."""
    fmt = str(arguments.get("format") or "").strip().lower()
    if fmt not in FORMATS:
        raise CreateError("format must be docx, pdf or xlsx.")
    title = _short(arguments.get("title"), MAX_TITLE)
    if not title:
        raise CreateError("title is required.")
    template = str(arguments.get("template") or "").strip().lower()
    if template not in TEMPLATES:
        template = "sheet" if fmt == "xlsx" else "report"
    spec = DocumentSpec(
        format=fmt,
        title=title,
        subtitle=_short(arguments.get("subtitle"), MAX_TITLE),
        author=_short(arguments.get("author"), 120) or "Agentic Runtime",
        template=template,
        filename=_filename(arguments, title, fmt),
        sections=_sections(arguments.get("sections")),
        sheets=_sheets(arguments.get("sheets")),
        theme=theme_for(template),
    )
    return _fill(spec)


def _fill(spec: DocumentSpec) -> DocumentSpec:
    sections = spec.sections
    sheets = spec.sheets
    if spec.format in {"docx", "pdf"} and not sections and sheets:
        sections = tuple(_section_from_sheet(sheet) for sheet in sheets)
    if spec.format == "xlsx" and not sheets:
        sheets = _sheets_from_sections(spec)
    if spec.format == "xlsx" and not sheets:
        sheets = (_cover(spec),)
    return replace(spec, sections=sections, sheets=sheets)


def _section_from_sheet(sheet: Sheet) -> Section:
    return Section(
        heading=sheet.name,
        level=1,
        paragraphs=(),
        bullets=(),
        table=Table(caption=sheet.name, columns=sheet.columns, rows=sheet.rows),
    )


def _sheets_from_sections(spec: DocumentSpec) -> tuple[Sheet, ...]:
    used: set[str] = set()
    sheets: list[Sheet] = []
    notes: list[tuple[Cell, ...]] = []
    for section in spec.sections:
        if section.table is not None:
            label = section.table.caption or section.heading
            sheets.append(
                Sheet(
                    name=_unique_sheet(label, used),
                    columns=section.table.columns,
                    rows=section.table.rows,
                )
            )
        prose = list(section.paragraphs)
        prose.extend(f"- {item}" for item in section.bullets)
        if prose:
            notes.append((Cell(section.heading, None), Cell(" ".join(prose), None)))
    if notes:
        sheets.append(
            Sheet(
                name=_unique_sheet("Notes", used),
                columns=("Heading", "Text"),
                rows=tuple(notes),
            )
        )
    return tuple(sheets)


def _cover(spec: DocumentSpec) -> Sheet:
    return Sheet(
        name="Cover",
        columns=("Field", "Value"),
        rows=(
            (Cell("Title", None), Cell(spec.title, None)),
            (Cell("Subtitle", None), Cell(spec.subtitle, None)),
            (Cell("Author", None), Cell(spec.author, None)),
        ),
    )


def _sections(raw: object) -> tuple[Section, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CreateError("sections must be a list.")
    if len(raw) > MAX_SECTIONS:
        raise CreateError(f"A document can have at most {MAX_SECTIONS} sections.")
    sections: list[Section] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise CreateError("Each section must be an object.")
        chosen = _heading_level(item.get("level"))
        sections.append(
            Section(
                heading=_short(item.get("heading"), MAX_TITLE) or f"Section {index}",
                level=chosen,
                paragraphs=_lines(item.get("paragraphs"), MAX_PARAGRAPHS, "paragraphs"),
                bullets=_lines(item.get("bullets"), MAX_BULLETS, "bullets"),
                table=_table(item.get("table")),
            )
        )
    return tuple(sections)


def _sheets(raw: object) -> tuple[Sheet, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CreateError("sheets must be a list.")
    if len(raw) > MAX_SHEETS:
        raise CreateError(f"A workbook can have at most {MAX_SHEETS} sheets.")
    used: set[str] = set()
    sheets: list[Sheet] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise CreateError("Each sheet must be an object.")
        columns, rows = _grid(item.get("columns"), item.get("rows"))
        sheets.append(
            Sheet(
                name=_unique_sheet(str(item.get("name") or f"Sheet {index}"), used),
                columns=columns,
                rows=rows,
            )
        )
    return tuple(sheets)


def _table(raw: object) -> Table | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CreateError("table must be an object.")
    if not raw.get("columns") and not raw.get("rows"):
        return None
    columns, rows = _grid(raw.get("columns"), raw.get("rows"))
    return Table(caption=_short(raw.get("caption"), MAX_TITLE), columns=columns, rows=rows)


def _grid(
    columns_raw: object, rows_raw: object
) -> tuple[tuple[str, ...], tuple[tuple[Cell, ...], ...]]:
    if rows_raw is not None and not isinstance(rows_raw, list):
        raise CreateError("rows must be a list.")
    rows = rows_raw if isinstance(rows_raw, list) else []
    if len(rows) > MAX_ROWS:
        raise CreateError(f"A table can have at most {MAX_ROWS} rows.")
    columns = _columns(columns_raw, rows)
    if len(columns) > MAX_COLUMNS:
        raise CreateError(f"A table can have at most {MAX_COLUMNS} columns.")
    return columns, tuple(_row(item, columns) for item in rows)


def _columns(raw: object, rows: list[object]) -> tuple[str, ...]:
    if isinstance(raw, list) and raw:
        names = [_short(item, 120) or f"Column {index}" for index, item in enumerate(raw, start=1)]
        return tuple(names)
    if rows and isinstance(rows[0], dict):
        return tuple(_short(key, 120) or "Column" for key in rows[0])
    if rows and isinstance(rows[0], list) and rows[0]:
        return tuple(f"Column {index}" for index in range(1, len(rows[0]) + 1))
    return ("Value",)


def _row(item: object, columns: tuple[str, ...]) -> tuple[Cell, ...]:
    if isinstance(item, dict):
        return tuple(_cell(item.get(column)) for column in columns)
    if isinstance(item, list):
        return tuple(
            _cell(item[index]) if index < len(item) else Cell("", None)
            for index in range(len(columns))
        )
    raise CreateError("Each row must be a list or an object.")


def _lines(raw: object, cap: int, label: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    items: list[object]
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        raise CreateError(f"{label} must be a list of strings.")
    if len(items) > cap:
        raise CreateError(f"A section can have at most {cap} {label}.")
    return tuple(text for text in (_short(item, MAX_TEXT) for item in items) if text)


def _cell(value: object) -> Cell:
    if isinstance(value, bool):
        return Cell("true" if value else "false", None)
    if isinstance(value, int):
        return Cell(str(value), float(value))
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return Cell("", None)
        return Cell(_number_text(value), value)
    return Cell(_short(value, MAX_TEXT), None)


def _filename(arguments: dict[str, object], title: str, fmt: str) -> str:
    raw = (
        arguments.get("fileName")
        or arguments.get("filename")
        or arguments.get("file_name")
        or arguments.get("path")
        or ""
    )
    picked = sanitise_name(Path(str(raw)).name) if str(raw).strip() else ""
    if not picked or picked == "artifact":
        picked = f"{_slug(title)}.{fmt}"
    suffix = f".{fmt}"
    if not picked.lower().endswith(suffix):
        stem = picked.rsplit(".", 1)[0] if "." in picked else picked
        picked = f"{stem}{suffix}"
    return sanitise_name(picked)


def _unique_sheet(name: str, used: set[str]) -> str:
    base = _safe_sheet(name)
    candidate = base
    number = 2
    while candidate.lower() in used:
        suffix = f" {number}"
        candidate = f"{base[: 31 - len(suffix)]}{suffix}"
        number += 1
    used.add(candidate.lower())
    return candidate


def _safe_sheet(name: str) -> str:
    cleaned = "".join(" " if char in "\\/?*[]:" else char for char in _short(name, 80))
    cleaned = " ".join(cleaned.split()).strip("' ")
    return (cleaned or "Sheet")[:31]


def _number_text(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _heading_level(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 1:
        return 1
    return 2


def _slug(title: str) -> str:
    cleaned = _SLUG.sub("-", title.lower()).strip("-")
    return (cleaned or "document")[:60]


def _short(value: object, limit: int) -> str:
    if value is None:
        return ""
    text = str(value)
    cleaned = []
    for char in text:
        if char >= " " or char in "\n\t":
            cleaned.append(" " if char in "\n\t" else char)
        else:
            cleaned.append(" ")
    compact = " ".join("".join(cleaned).split())
    if len(compact) <= limit:
        return compact
    if limit <= 3:
        return compact[:limit]
    return compact[: limit - 3] + "..."
