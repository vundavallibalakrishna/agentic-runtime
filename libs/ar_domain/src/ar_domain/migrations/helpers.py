"""RLS and trigger helpers. Spec: docs/04-data/rls.md §3, docs/04-data/migrations.md §2."""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Iterable


def enable_tenant_rls(table: str) -> None:
    """Tenant isolation policy for tables with ``tenant_id NOT NULL``."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (tenant_id = app_tenant_id()) "
        "WITH CHECK (tenant_id = app_tenant_id())"
    )


def enable_platform_or_own_rls(table: str) -> None:
    """Read platform rows; write only the caller's tenant rows."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY read_platform_or_own ON {table} FOR SELECT "
        "USING (tenant_id IS NULL OR tenant_id = app_tenant_id())"
    )
    op.execute(
        f"CREATE POLICY write_own ON {table} FOR ALL "
        "USING (tenant_id = app_tenant_id()) "
        "WITH CHECK (tenant_id = app_tenant_id())"
    )


def enable_audit_rls(table: str) -> None:
    """Select and insert policies for nullable-tenant append-only tables."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_read ON " + table + " FOR SELECT USING (tenant_id = app_tenant_id())"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON "
        + table
        + " FOR INSERT WITH CHECK (tenant_id = app_tenant_id())"
    )


def add_updated_at_trigger(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER set_updated_at BEFORE UPDATE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def add_append_only_trigger(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION forbid_update_delete()"
    )


def grant_table(table: str, *, append_only: bool = False) -> None:
    """Grant the three service roles. ``ar_app`` cannot update append-only tables."""
    if append_only:
        op.execute(f"GRANT SELECT, INSERT ON {table} TO ar_app")
    else:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO ar_app")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO ar_platform")
    op.execute(f"GRANT SELECT ON {table} TO ar_readonly")


def grant_tables(tables: Iterable[str], *, append_only: Iterable[str] = ()) -> None:
    frozen = set(append_only)
    for table in tables:
        grant_table(table, append_only=table in frozen)
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ar_app, ar_platform")
    op.execute("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO ar_readonly")
