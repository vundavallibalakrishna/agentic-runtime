"""Keep every version of a knowledge document that a source sync fetched.

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-23

A knowledge document is one row per item of its source. When the item changed, the sync
replaced the bytes it held, and held them only in the memory of the process that
fetched them, so no earlier version could be read and the current one was lost on a
restart. The sync now stores each fetched body as a file, and ``document_revisions``
records which file each version of a document was, with what was measured when it was
fetched. The table is generic: any source kind writes it, and it has no column that
says what a document is about.

Expand only: one new table. Downgrade drops it; the files it pointed at are left.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import enable_tenant_rls, grant_table

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_revisions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=True),
        sa.Column("version_hash", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_document_revisions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_revisions_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name=op.f("fk_document_revisions_file_id_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_revisions")),
    )
    op.create_index(
        "ix_document_revisions_document",
        "document_revisions",
        ["tenant_id", "document_id", sa.text("captured_at DESC")],
    )
    enable_tenant_rls("document_revisions")
    grant_table("document_revisions")


def downgrade() -> None:
    op.drop_index("ix_document_revisions_document", table_name="document_revisions")
    op.drop_table("document_revisions")
