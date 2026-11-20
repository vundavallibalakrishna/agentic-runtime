"""Table files, read a row at a time.

A CSV, TSV or xlsx file is never held whole: ``TableSource.rows`` opens the file again
and yields one row after another, so a long file costs the reader the same memory as a
short one. A JSON file is parsed once, because its columns are only known after every
object has been seen. Cell content is data.
"""

from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
MAX_COLUMNS = 64
TABLE_SUFFIXES = frozenset({".csv", ".tsv", ".json", ".xlsx"})


@dataclass(frozen=True, slots=True)
class TableSource:
    """One table of a file: its name, its columns, and a way to read its rows again.

    Every row ``rows()`` yields has exactly one cell for each column.
    """

    name: str
    columns: list[str]
    rows: Callable[[], Iterator[list[object]]]


class TableTooLongError(Exception):
    """A table has more rows than the table tools read."""

    def __init__(self, table: str, limit: int) -> None:
        self.table = table
        self.limit = limit
        super().__init__(f"{table} has more than {limit} rows")


def max_table_rows() -> int:
    """The most rows of one table the table tools read (``AR_TABLE_MAX_ROWS``)."""
    from ar_common.settings import get_settings  # noqa: PLC0415

    return int(get_settings().table_max_rows)


def bounded(source: TableSource, limit: int) -> Iterator[list[object]]:
    """The rows of ``source``. Reading past ``limit`` rows raises ``TableTooLongError``.

    A count, a total or a sample over the first rows of a longer table is a wrong answer
    that looks right, so a table over the limit is refused, never read in part.
    """
    for index, row in enumerate(source.rows()):
        if index >= limit:
            raise TableTooLongError(source.name, limit)
        yield row


def read_book(path: Path) -> list[TableSource]:
    """The tables of one file: one for a CSV, TSV or JSON file, one a sheet for xlsx."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _xlsx_tables(path)
    if suffix == ".json":
        return [_json_table(path)]
    return [_delimited_table(path, "\t" if suffix == ".tsv" else ",")]


def table_name(name: str) -> str:
    """A file or sheet name as an identifier a statement can put after FROM."""
    cleaned = re.sub(r"[^a-z0-9_]", "_", name.lower())
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    cleaned = cleaned[:60]
    if not _IDENT.fullmatch(cleaned):
        return "sheet"
    return cleaned


def column_name(name: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"col_{index}"
    return cleaned[:60]


def _header(cells: list[str]) -> list[str]:
    named = [column_name(str(item) or f"col_{index}", index) for index, item in enumerate(cells)]
    return named[:MAX_COLUMNS]


def _fit(row: list[str], width: int) -> list[object]:
    fitted: list[object] = list(row[:width])
    fitted.extend([""] * (width - len(fitted)))
    return fitted


def _delimited_table(path: Path, delimiter: str) -> TableSource:
    def lines() -> Iterator[list[str]]:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            yield from csv.reader(handle, delimiter=delimiter)

    columns = _header(next(lines(), []))

    def rows() -> Iterator[list[object]]:
        body = lines()
        next(body, None)
        for row in body:
            yield _fit(row, len(columns))

    return TableSource(table_name(path.stem), columns, rows)


def _json_table(path: Path) -> TableSource:
    objects = _json_objects(path.read_bytes())
    columns: list[str] = []
    for item in objects:
        for key in item:
            name = column_name(str(key), len(columns))
            if name not in columns:
                columns.append(name)

    def rows() -> Iterator[list[object]]:
        for item in objects:
            yield [item.get(column) for column in columns]

    return TableSource(table_name(path.stem), columns, rows)


def _json_objects(data: bytes) -> list[dict[str, object]]:
    import orjson  # noqa: PLC0415

    parsed = orjson.loads(data)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return [item for item in value if isinstance(item, dict)]
        return [parsed]
    raise ValueError("json must be a list of objects")


def _xlsx_tables(path: Path) -> list[TableSource]:
    with zipfile.ZipFile(path) as book:
        sheets = sheet_map(book)
        present = set(book.namelist())
    found = [
        _sheet_table(path, name or path.stem, target)
        for name, target in sheets
        if target in present
    ]
    return found or [TableSource(table_name(path.stem), [], lambda: iter(()))]


def _sheet_table(path: Path, name: str, target: str) -> TableSource:
    def lines() -> Iterator[list[str]]:
        with zipfile.ZipFile(path) as book, book.open(target) as stream:
            yield from sheet_rows(stream, shared_strings(book))

    columns = _header(next(lines(), []))

    def rows() -> Iterator[list[object]]:
        body = lines()
        next(body, None)
        for row in body:
            yield _fit(row, len(columns))

    return TableSource(table_name(name), columns, rows)


def shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(book.read("xl/sharedStrings.xml"))  # noqa: S314
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.iter(f"{_NS}t")) for item in root.iter(f"{_NS}si")
    ]


def sheet_map(book: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Each worksheet's name and the archive member that holds it."""
    try:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))  # noqa: S314
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))  # noqa: S314
    except KeyError:
        return [("sheet1", "xl/worksheets/sheet1.xml")]
    targets = {node.attrib.get("Id"): node.attrib.get("Target", "") for node in rels}
    found: list[tuple[str, str]] = []
    for sheet in workbook.iter(f"{_NS}sheet"):
        target = targets.get(sheet.attrib.get(f"{_OFFICE_REL}id") or "", "")
        if target and not target.startswith("xl/"):
            target = f"xl/{target.lstrip('/')}"
        if target:
            found.append((sheet.attrib.get("name") or "sheet", target))
    return found or [("sheet1", "xl/worksheets/sheet1.xml")]


def sheet_rows(stream: IO[bytes], shared: list[str]) -> Iterator[list[str]]:
    """The rows of one worksheet that hold a cell, each freed once it has been yielded."""
    for _event, node in ET.iterparse(stream, events=("end",)):  # noqa: S314
        if node.tag != f"{_NS}row":
            continue
        cells: dict[int, str] = {}
        for cell in node.findall(f"{_NS}c"):
            cells[_column_index(cell.attrib.get("r", ""))] = _cell_text(cell, shared)
        node.clear()
        if cells:
            width = min(max(cells) + 1, MAX_COLUMNS)
            yield [cells.get(position, "") for position in range(width)]


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{_NS}t"))
    value = cell.find(f"{_NS}v")
    raw = "" if value is None or value.text is None else value.text
    if kind == "s" and raw.isdigit():
        pointer = int(raw)
        return shared[pointer] if pointer < len(shared) else raw
    return raw


def _column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    number = 0
    for ch in letters:
        number = number * 26 + ord(ch.upper()) - 64
    return max(0, number - 1)
