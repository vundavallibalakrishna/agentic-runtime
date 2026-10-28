"""grc schema, the 27 domain tables, and the entity tree.

Revision ID: 0001
Revises:
Create Date: 2026-10-28

M16-T07 entity columns ship in this revision so the pack head matches the models.
Core revisions are not touched.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls
from ar_pack_grc.models import TABLES_WITH_UPDATED_AT, PackBase

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _external(name: str) -> None:
    """Core tables the foreign keys point at. They already exist and are not created."""
    if name in PackBase.metadata.tables:
        return
    sa.Table(name, PackBase.metadata, sa.Column("id", UUID(as_uuid=True), primary_key=True))


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS grc")
    op.execute("GRANT USAGE ON SCHEMA grc TO ar_app, ar_platform, ar_readonly")
    for name in ("tenants", "users", "evidence_items"):
        _external(name)
    bind = op.get_bind()
    PackBase.metadata.create_all(bind)
    for table in PackBase.metadata.tables.values():
        if table.schema == "grc":
            enable_tenant_rls(f"grc.{table.name}")
    for name in TABLES_WITH_UPDATED_AT:
        add_updated_at_trigger(f"grc.{name}")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA grc TO ar_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA grc TO ar_platform")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA grc TO ar_readonly")


def downgrade() -> None:
    bind = op.get_bind()
    grc_tables = [table for table in PackBase.metadata.sorted_tables if table.schema == "grc"]
    for table in reversed(grc_tables):
        table.drop(bind, checkfirst=True)
    op.execute("DROP SCHEMA IF EXISTS grc CASCADE")
