"""In-process DuckDB for workspace tables.

The connection is memory-only. External file access is turned off before any
statement, including the caller's SQL. Values are loaded from Python, not from
``read_csv``.
"""

from __future__ import annotations

import duckdb

_MAX_IDENT = 60


class SheetQueryError(Exception):
    """DuckDB rejected the statement or could not run it."""

    def __init__(self, reason: str, *, rejected: bool = False) -> None:
        self.reason = reason
        self.rejected = rejected
        super().__init__(reason)


def query_loaded(
    sheets: list[tuple[str, list[str], list[list[object]]]],
    sql: str,
    *,
    row_limit: int,
) -> tuple[list[str], list[list[object]], bool]:
    """Run one already-guarded statement. Returns columns, rows and truncation."""
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("SET enable_external_access = false")
        _declare(connection, sheets)
        try:
            connection.execute(sql)
        except duckdb.Error as exc:
            raise _failed(exc) from exc
        description = connection.description or []
        columns = [str(item[0]) for item in description]
        try:
            raw = connection.fetchmany(row_limit + 1)
        except duckdb.Error as exc:
            raise _failed(exc) from exc
    finally:
        connection.close()
    truncated = len(raw) > row_limit
    rows = [list(item) for item in raw[:row_limit]]
    return columns, rows, truncated


def _declare(
    connection: duckdb.DuckDBPyConnection,
    sheets: list[tuple[str, list[str], list[list[object]]]],
) -> None:
    for table, columns, rows in sheets:
        if not columns:
            continue
        kinds = [_kind(index, rows) for index in range(len(columns))]
        declared = ", ".join(
            f'"{_quote(column)}" {kind}' for column, kind in zip(columns, kinds, strict=True)
        )
        connection.execute(f'CREATE TABLE "{_quote(table)}" ({declared})')
        placeholders = ", ".join("?" for _ in columns)
        payload = [_bound(row, kinds) for row in rows]
        connection.executemany(
            f'INSERT INTO "{_quote(table)}" VALUES ({placeholders})',  # noqa: S608
            payload,
        )


def _bound(row: list[object], kinds: list[str]) -> list[object]:
    values: list[object] = []
    for index, kind in enumerate(kinds):
        cell = row[index] if index < len(row) else None
        values.append(_coerce(cell, kind))
    return values


def _coerce(value: object, kind: str) -> object:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if kind == "BIGINT":
        return int(text)
    if kind == "DOUBLE":
        return float(text.replace(",", ""))
    return str(value)


def _kind(index: int, rows: list[list[object]]) -> str:
    present = [
        row[index]
        for row in rows
        if index < len(row) and str(row[index]).strip() not in {"", "None"}
    ]
    if present and all(_intish(item) for item in present):
        return "BIGINT"
    if present and all(_floaty(item) for item in present):
        return "DOUBLE"
    return "VARCHAR"


def _intish(value: object) -> bool:
    text = str(value).strip()
    if text.startswith(("+", "-")):
        text = text[1:]
    if not text.isdigit():
        return False
    return not (len(text) > 1 and text.startswith("0"))


def _floaty(value: object) -> bool:
    text = str(value).strip().replace(",", "")
    if text.count(".") != 1:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def _quote(name: str) -> str:
    return name.replace('"', "")[:_MAX_IDENT]


def _failed(exc: duckdb.Error) -> SheetQueryError:
    message = str(exc).split("\n", maxsplit=1)[0][:300]
    lowered = message.lower()
    rejected = (
        type(exc).__name__ == "PermissionException"
        or "file system" in lowered
        or "external access" in lowered
    )
    return SheetQueryError(message or "the query failed", rejected=rejected)
