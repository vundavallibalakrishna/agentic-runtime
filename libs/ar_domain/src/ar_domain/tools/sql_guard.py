"""Read-only SQL guard. The connector package exposes the same rules."""

from sqlglot import exp, parse
from sqlglot.errors import ParseError

_DENY = frozenset(
    {
        "pg_sleep",
        "pg_sleep_for",
        "pg_sleep_until",
        "dblink",
        "dblink_exec",
        "dblink_connect",
        "lo_import",
        "lo_export",
        "lo_unlink",
        "copy",
        "xp_cmdshell",
        "xp_regread",
        "xp_fileexist",
        "load_file",
        "sleep",
        "benchmark",
    }
)
_WRITE = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Merge,
    exp.Grant,
)


class SqlRejected(Exception):  # noqa: N818
    """The statement is not a single allowlisted read."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def check_sql(  # noqa: PLR0912
    sql: str,
    *,
    allow_tables: set[str],
    deny_columns: set[str],
    row_limit: int = 1000,
    dialect: str = "postgres",
) -> str:
    """Return the statement with a limit, or raise ``SqlRejected``."""
    try:
        trees = [item for item in parse(sql, dialect=dialect) if item is not None]
    except ParseError as exc:
        raise SqlRejected("could not parse") from exc
    if len(trees) != 1:
        raise SqlRejected("exactly one statement")
    tree = trees[0]
    if tree.find(*_WRITE) is not None or tree.find(exp.Into) is not None:
        raise SqlRejected("only a single select is allowed")
    if not isinstance(tree, exp.Select | exp.Union):
        raise SqlRejected("only a single select is allowed")
    if tree.args.get("for") is not None:
        raise SqlRejected("locking reads are not allowed")
    for func in tree.find_all(exp.Anonymous, exp.Func):
        name = func.name.lower() if isinstance(func.name, str) else ""
        if name in _DENY or name.startswith("dblink") or name.startswith("lo_"):
            raise SqlRejected(f"function {name or 'call'} is not allowed")
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in ctes:
            continue
        schema = (table.db or "public").lower()
        qualified = f"{schema}.{name}"
        if qualified not in allow_tables and name not in allow_tables:
            raise SqlRejected(f"table {qualified} is not allowlisted")
        if tree.find(exp.Star) is not None and any(
            item.startswith(f"{qualified}.") for item in deny_columns
        ):
            raise SqlRejected(f"select * includes a denied column on {qualified}")
    for column in tree.find_all(exp.Column):
        if not column.name:
            continue
        table_name = (column.table or "").lower()
        column_name = column.name.lower()
        for denied in deny_columns:
            parts = denied.lower().split(".")
            if parts[-1] != column_name:
                continue
            if len(parts) >= 2 and table_name and parts[-2] not in {table_name, ""}:
                continue
            raise SqlRejected(f"column {denied} is denied")
    if isinstance(tree, exp.Select) and tree.args.get("limit") is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(row_limit + 1)))
    return tree.sql(dialect=dialect)
