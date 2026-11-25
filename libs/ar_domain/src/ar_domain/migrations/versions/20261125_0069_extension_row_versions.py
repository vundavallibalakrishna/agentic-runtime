"""Version and reason on pack rows, plus an append-only history.

Revision ID: 0069
Revises: 0068
Create Date: 2026-11-25

The current row stays on ``extension_rows``. Each save also inserts a history
row that downgrade drops. Existing rows become version 1 with an empty reason.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from ar_domain.migrations.helpers import enable_tenant_rls, grant_table

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "extension_rows",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "extension_rows",
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
    )
    op.create_table(
        "extension_row_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("row_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extension_row_versions")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_extension_row_versions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_extension_row_versions_row",
        "extension_row_versions",
        ["tenant_id", "row_id", "version"],
    )
    enable_tenant_rls("extension_row_versions")
    grant_table("extension_row_versions")


def downgrade() -> None:
    op.drop_index("ix_extension_row_versions_row", table_name="extension_row_versions")
    op.drop_table("extension_row_versions")
    op.drop_column("extension_rows", "reason")
    op.drop_column("extension_rows", "version")
