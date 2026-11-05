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
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_terminate_backend",
        "nextval",
        "setval",
        "set_config",
        "writefile",
        "readfile",
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
    exp.Copy,
)
_SYSTEM = frozenset({"pg_catalog", "information_schema", "pg_toast"})
_DUCK_FUNCS = frozenset(
    {
        "glob",
        "getenv",
        "current_setting",
        "load_aws_credentials",
        "read_blob",
        "read_csv",
        "read_csv_auto",
        "read_json",
        "read_json_auto",
        "read_json_objects",
        "read_parquet",
        "read_text",
    }
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
    allow_any: bool = False,
    allow_schemas: set[str] | None = None,
    allow_system: bool = False,
) -> str:
    """Return the statement with a limit, or raise ``SqlRejected``."""
    try:
        trees = [item for item in parse(sql, dialect=dialect) if item is not None]
    except ParseError as exc:
        raise SqlRejected("could not parse") from exc
    if len(trees) != 1:
        raise SqlRejected("exactly one statement")
    tree = trees[0]
    _reject_file_reads(tree, dialect)
    if tree.find(*_WRITE) is not None or tree.find(exp.Into) is not None:
        raise SqlRejected("only a single select is allowed")
    shapes: tuple[type[exp.Expression], ...] = (exp.Select, exp.Union)
    if dialect == "duckdb":
        shapes = (exp.Select, exp.Union, exp.Pivot)
    if not isinstance(tree, shapes):
        raise SqlRejected("only a single select is allowed")
    if tree.args.get("for") is not None:
        raise SqlRejected("locking reads are not allowed")
    for func in tree.find_all(exp.Anonymous, exp.Func):
        name = func.name.lower() if isinstance(func.name, str) else ""
        if name in _DENY or name.startswith("dblink") or name.startswith("lo_"):
            raise SqlRejected(f"function {name or 'call'} is not allowed")
        if dialect == "duckdb" and _duck_blocked(name):
            raise SqlRejected(f"function {name or 'call'} is not allowed")
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in ctes:
            continue
        schema = (table.db or "public").lower()
        qualified = f"{schema}.{name}"
        if not allow_system and (schema in _SYSTEM or name.startswith("pg_")):
            raise SqlRejected(f"table {qualified} is not available")
        if allow_schemas and schema not in allow_schemas:
            raise SqlRejected(f"schema {schema} is not allowed for this agent")
        if not allow_any and qualified not in allow_tables and name not in allow_tables:
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


def _reject_file_reads(tree: exp.Expr, dialect: str) -> None:
    """Reject readers that can escape the loaded tables."""
    if tree.find(exp.ReadCSV, exp.ReadParquet) is not None:
        raise SqlRejected("file reads are not allowed")
    if dialect != "duckdb":
        return
    for func in tree.find_all(exp.Anonymous):
        name = func.name.lower() if isinstance(func.name, str) else ""
        if _duck_blocked(name):
            raise SqlRejected(f"function {name or 'call'} is not allowed")


def _duck_blocked(name: str) -> bool:
    return bool(
        name
        and (name in _DUCK_FUNCS or name.startswith(("read_", "duckdb_")) or name.endswith("_scan"))
    )
