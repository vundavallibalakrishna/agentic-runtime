"""M19 inspection, privacy and resilience tables, plus asset inventory columns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28

Databases that already applied 0001 keep their rows. New tables and columns are
created only when missing, so a current 0001 (which creates PackBase as it
stands) and an older 0001 both reach the same head. Core Alembic is untouched.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import enable_tenant_rls, grant_table
from ar_pack_grc.models import PackBase

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = ("inspections", "dsar_requests", "consent_records", "resilience_tests")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names(schema="grc"))
    for name in _NEW_TABLES:
        if name in existing:
            continue
        PackBase.metadata.tables[f"grc.{name}"].create(bind)
        enable_tenant_rls(f"grc.{name}")
        grant_table(f"grc.{name}")
    _asset_columns(inspector)
    _pbc_status()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("assets", schema="grc")}
    if "tier" in columns:
        op.drop_column("assets", "tier", schema="grc")
    if "agent_card_id" in columns:
        op.drop_column("assets", "agent_card_id", schema="grc")
    op.execute(
        """
        DO $$
        DECLARE constraint_name text;
        BEGIN
          FOR constraint_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'grc'
              AND rel.relname = 'pbc_requests'
              AND con.contype = 'c'
              AND pg_get_constraintdef(con.oid) ILIKE '%status%'
          LOOP
            EXECUTE format('ALTER TABLE grc.pbc_requests DROP CONSTRAINT %I', constraint_name);
          END LOOP;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE grc.pbc_requests ADD CONSTRAINT ck_pbc_requests_status "
        "CHECK (status IN ('open', 'responded', 'accepted'))"
    )
    for name in reversed(_NEW_TABLES):
        op.execute(f"DROP TABLE IF EXISTS grc.{name}")


def _asset_columns(inspector: sa.Inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("assets", schema="grc")}
    asset = PackBase.metadata.tables["grc.assets"]
    for name in ("agent_card_id", "tier"):
        if name in columns:
            continue
        op.add_column("assets", _copy(asset.c[name]), schema="grc")


def _copy(column: sa.Column[object]) -> sa.Column[object]:
    return sa.Column(column.name, column.type, nullable=column.nullable)


def _pbc_status() -> None:
    table = PackBase.metadata.tables["grc.pbc_requests"]
    check = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint) and "status" in str(constraint.sqltext)
    )
    op.execute(
        """
        DO $$
        DECLARE constraint_name text;
        BEGIN
          FOR constraint_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'grc'
              AND rel.relname = 'pbc_requests'
              AND con.contype = 'c'
              AND pg_get_constraintdef(con.oid) ILIKE '%status%'
          LOOP
            EXECUTE format('ALTER TABLE grc.pbc_requests DROP CONSTRAINT %I', constraint_name);
          END LOOP;
        END $$;
        """
    )
    name = check.name or "ck_pbc_requests_status"
    op.execute(f"ALTER TABLE grc.pbc_requests ADD CONSTRAINT {name} CHECK ({check.sqltext})")
