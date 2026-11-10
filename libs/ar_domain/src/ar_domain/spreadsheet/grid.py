"""Read an xlsx grid with the original header text.

Spreadsheet SQL sanitises names so they are identifiers. A sheet fill
keeps the headers the user will see in the downloaded file.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from ar_domain.tools.analysis import _shared, _sheet_map, _sheet_rows


@dataclass(frozen=True)
class Grid:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def grids_from_xlsx(data: bytes, *, max_rows: int = 500) -> list[Grid]:
    """Return each worksheet. The first row is the header."""
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        shared = _shared(book)
        found: list[Grid] = []
        for name, target in _sheet_map(book):
            try:
                xml = book.read(target)
            except KeyError:
                continue
            raw = _sheet_rows(xml, shared)
            if not raw:
                continue
            columns = _headers(raw[0])
            body: list[tuple[str, ...]] = []
            for row in raw[1 : max_rows + 1]:
                padded = list(row) + [""] * (len(columns) - len(row))
                body.append(tuple(str(cell) for cell in padded[: len(columns)]))
            found.append(Grid(name=name or "Sheet", columns=columns, rows=tuple(body)))
        return found


def _headers(row: list[str]) -> tuple[str, ...]:
    names: list[str] = []
    used: set[str] = set()
    for index, cell in enumerate(row, start=1):
        label = str(cell).strip() or f"Column {index}"
        candidate = label
        number = 2
        while candidate.lower() in used:
            candidate = f"{label} {number}"
            number += 1
        used.add(candidate.lower())
        names.append(candidate[:120])
    return tuple(names)
