"""Durable rows for packs.

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-16

A pack keeps its rows here so the API and the worker share them. The table is
generic: the pack id and bucket live in columns, and the industry words stay in
the pack. Restart processes after upgrading so they load the new table.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_table

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extension_rows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extension_rows")),
    )
    op.create_index(
        "ix_extension_rows_tenant_pack",
        "extension_rows",
        ["tenant_id", "pack_id", "bucket"],
    )
    enable_tenant_rls("extension_rows")
    add_updated_at_trigger("extension_rows")
    grant_table("extension_rows")


def downgrade() -> None:
    op.drop_index("ix_extension_rows_tenant_pack", table_name="extension_rows")
    op.drop_table("extension_rows")
