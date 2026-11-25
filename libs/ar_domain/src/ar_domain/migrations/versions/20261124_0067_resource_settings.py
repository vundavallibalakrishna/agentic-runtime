"""Versioned settings documents checked against a JSON Schema.

Revision ID: 0067
Revises: 0066
Create Date: 2026-11-24

A pack or an agent may declare a JSON Schema for a settings document. Each save
appends a version. The table has no domain columns.

Expand only. Downgrade drops the table.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import enable_tenant_rls, grant_table

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_settings",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema", postgresql.JSONB(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_resource_settings_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_settings")),
        sa.UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "version",
            name="uq_resource_settings_version",
        ),
    )
    enable_tenant_rls("resource_settings")
    grant_table("resource_settings")


def downgrade() -> None:
    op.drop_table("resource_settings")
