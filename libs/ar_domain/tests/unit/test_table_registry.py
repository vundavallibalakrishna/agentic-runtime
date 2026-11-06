"""Every module that maps a table is in the registry each process loads."""

from pathlib import Path

from sqlalchemy.orm import configure_mappers

import ar_domain
from ar_domain.db.base import Base
from ar_domain.db.registry import TABLE_MODULES, import_models

SOURCE = Path(ar_domain.__file__).resolve().parent


def _modules_with_tables() -> set[str]:
    found: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        if "__tablename__" in path.read_text(encoding="utf-8"):
            relative = path.relative_to(SOURCE).with_suffix("")
            found.add("ar_domain." + ".".join(relative.parts))
    return found


def test_registry_lists_every_table_module() -> None:
    assert set(TABLE_MODULES) == _modules_with_tables()
    assert len(TABLE_MODULES) == len(set(TABLE_MODULES))


def test_every_foreign_key_resolves_after_import() -> None:
    """The failure a partly loaded process hits: a foreign key to an unknown table."""
    import_models()
    configure_mappers()
    for table in Base.metadata.tables.values():
        for key in table.foreign_keys:
            assert key.column.table.name in Base.metadata.tables
