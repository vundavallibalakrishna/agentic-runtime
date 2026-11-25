"""Keep each extraction of a document.

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-24

An extraction used to exist only in the answer that produced it. This table keeps
the schema hash, the file hash, the model alias and the per-field result so a
later read can show what was extracted and what a person corrected.

Expand only. Downgrade drops the table.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import enable_tenant_rls, grant_table

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("content_hash", sa.Text(), server_default="", nullable=False),
        sa.Column("schema_hash", sa.Text(), server_default="", nullable=False),
        sa.Column("model_alias", sa.Text(), server_default="", nullable=False),
        sa.Column("strategy", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "fields",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "corrections",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("approval_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_document_extractions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_extractions")),
    )
    op.create_index(
        "ix_document_extractions_document",
        "document_extractions",
        ["tenant_id", "document_id", sa.text("created_at DESC")],
    )
    enable_tenant_rls("document_extractions")
    grant_table("document_extractions")


def downgrade() -> None:
    op.drop_index("ix_document_extractions_document", table_name="document_extractions")
    op.drop_table("document_extractions")
