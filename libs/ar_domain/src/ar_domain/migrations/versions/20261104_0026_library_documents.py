"""Durable extracted documents.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-04
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "library_documents",
    "document_checks",
    "document_comparisons",
    "document_rewrites",
)


def upgrade() -> None:
    op.create_table(
        "library_documents",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ready'"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "passages",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tables",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('upload','workspace','connection')",
            name=op.f("ck_library_documents_source"),
        ),
        sa.CheckConstraint(
            "status IN ('ready','failed')",
            name=op.f("ck_library_documents_status"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_library_documents_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_library_documents_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library_documents")),
        sa.UniqueConstraint(
            "tenant_id",
            "content_hash",
            name=op.f("uq_library_documents_content_hash"),
        ),
    )
    op.create_index(
        "ix_library_documents_tenant_created",
        "library_documents",
        ["tenant_id", "created_at"],
    )
    op.create_table(
        "document_checks",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("standard_document_id", sa.UUID(), nullable=True),
        sa.Column("label", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "rows",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_document_checks_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["library_documents.id"],
            name=op.f("fk_document_checks_document_id_library_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["standard_document_id"],
            ["library_documents.id"],
            name=op.f("fk_document_checks_standard_document_id_library_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_document_checks_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_checks")),
    )
    op.create_index(
        "ix_document_checks_document",
        "document_checks",
        ["tenant_id", "document_id"],
    )
    op.create_table(
        "document_comparisons",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("left_id", sa.UUID(), nullable=False),
        sa.Column("right_id", sa.UUID(), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_document_comparisons_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["left_id"],
            ["library_documents.id"],
            name=op.f("fk_document_comparisons_left_id_library_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["right_id"],
            ["library_documents.id"],
            name=op.f("fk_document_comparisons_right_id_library_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_document_comparisons_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_comparisons")),
    )
    op.create_table(
        "document_rewrites",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("anchor", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "passage_anchors",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("instruction", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("original", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("proposed", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "hunks",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('proposed','accepted','rejected')",
            name=op.f("ck_document_rewrites_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_document_rewrites_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["library_documents.id"],
            name=op.f("fk_document_rewrites_document_id_library_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_document_rewrites_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_rewrites")),
    )
    for table in _TABLES:
        add_updated_at_trigger(table)
        enable_tenant_rls(table)
    grant_tables(_TABLES)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
