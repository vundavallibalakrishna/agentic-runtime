"""In-process DuckDB for workspace tables.

The connection is memory-only. External file access is turned off before any
statement, including the caller's SQL. Values are loaded from Python a row at a
time, not from ``read_csv``, so a long file is never held in Python whole.
"""

from __future__ import annotations

import duckdb

from ar_domain.spreadsheet.source import TableSource, TableTooLongError, bounded

_MAX_IDENT = 60
_BATCH = 10_000
_INT_DIGITS = 18


class SheetQueryError(Exception):
    """DuckDB rejected the statement or could not run it."""

    def __init__(self, reason: str, *, rejected: bool = False) -> None:
        self.reason = reason
        self.rejected = rejected
        super().__init__(reason)


def query_tables(
    sources: list[TableSource],
    sql: str,
    *,
    row_limit: int,
    max_rows: int,
) -> tuple[list[str], list[list[object]], bool]:
    """Run one already-guarded statement. Returns columns, rows and truncation.

    Each table is read whole into the engine, a row at a time. A table of more than
    ``max_rows`` rows is refused before the statement runs.
    """
    names = [source.name for source in sources]
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("SET enable_external_access = false")
        for source in sources:
            _declare(connection, source, max_rows)
        try:
            connection.execute(sql)
        except duckdb.Error as exc:
            raise _failed(exc, names) from exc
        description = connection.description or []
        columns = [str(item[0]) for item in description]
        try:
            raw = connection.fetchmany(row_limit + 1)
        except duckdb.Error as exc:
            raise _failed(exc, names) from exc
    finally:
        connection.close()
    truncated = len(raw) > row_limit
    rows = [list(item) for item in raw[:row_limit]]
    return columns, rows, truncated


def measure(source: TableSource, max_rows: int) -> tuple[list[str], int]:
    """The engine type of each column and the number of rows, from one read of the table.

    A column is a number only when every value in it is one, so the whole table is read.
    """
    width = len(source.columns)
    present = [False] * width
    whole = [True] * width
    decimal = [True] * width
    count = 0
    try:
        for row in bounded(source, max_rows):
            count += 1
            for index in range(width):
                if not (whole[index] or decimal[index]):
                    continue
                cell = row[index]
                if str(cell).strip() in {"", "None"}:
                    continue
                present[index] = True
                whole[index] = whole[index] and _intish(cell)
                # A column of 3 and 1.5 is a column of numbers.
                decimal[index] = decimal[index] and (_floaty(cell) or _intish(cell))
    except TableTooLongError as exc:
        raise too_long(exc) from exc
    kinds = [
        "VARCHAR"
        if not present[index]
        else "BIGINT"
        if whole[index]
        else "DOUBLE"
        if decimal[index]
        else "VARCHAR"
        for index in range(width)
    ]
    return kinds, count


def too_long(exc: TableTooLongError) -> SheetQueryError:
    return SheetQueryError(
        f"{exc.table} has more than {exc.limit} rows, the most the table tools read. "
        "Nothing was run, because a count or a total over part of the file would be wrong. "
        "Say so to the person. An administrator can raise the limit, or the file can be "
        "given in smaller parts."
    )


def _declare(connection: duckdb.DuckDBPyConnection, source: TableSource, max_rows: int) -> None:
    if not source.columns:
        return
    kinds, _count = measure(source, max_rows)
    declared = ", ".join(
        f'"{_quote(column)}" {kind}' for column, kind in zip(source.columns, kinds, strict=True)
    )
    table = _quote(source.name)
    connection.execute(f'CREATE TABLE "{table}" ({declared})')
    appender = connection.appender(table)
    batch: list[list[object]] = []
    for row in source.rows():
        batch.append([_coerce(cell, kind) for cell, kind in zip(row, kinds, strict=True)])
        if len(batch) >= _BATCH:
            appender.append_rows(batch)
            batch = []
    appender.append_rows(batch)
    appender.flush()


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


def _intish(value: object) -> bool:
    text = str(value).strip()
    if text.startswith(("+", "-")):
        text = text[1:]
    if not text.isdigit() or len(text) > _INT_DIGITS:
        # A longer run of digits is an identifier, and would not fit the integer type.
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


def _advice(lowered: str, tables: list[str]) -> str:
    """What to change, for the two errors a statement over table files most often meets."""
    if "table with name" in lowered and "does not exist" in lowered:
        return (
            f" The tables loaded are: {', '.join(tables) or 'none'}. A statement that reads "
            "another file needs that file in paths as well."
        )
    if "varchar" in lowered and "candidate function" in lowered:
        return (
            " A column read from a file is text unless every value is a number. Cast it "
            "first, for example CAST(posted AS DATE) for a date."
        )
    return ""


def _quote(name: str) -> str:
    return name.replace('"', "")[:_MAX_IDENT]


def _failed(exc: duckdb.Error, tables: list[str]) -> SheetQueryError:
    message = str(exc).split("\n", maxsplit=1)[0][:300]
    lowered = message.lower()
    message = f"{message}{_advice(lowered, tables)}"
    rejected = (
        type(exc).__name__ == "PermissionException"
        or "file system" in lowered
        or "external access" in lowered
    )
    return SheetQueryError(message or "the query failed", rejected=rejected)
