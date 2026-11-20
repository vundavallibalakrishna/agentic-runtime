"""Layout columns on the one document row.

Revision ID: 0057
Revises: 0056
Create Date: 2026-11-20

Library extracts and knowledge documents are one row. ``documents`` gains the
layout (passages, tables, outline) and may exist without a collection. Existing
library rows are copied onto that table, keeping their id when it is free.
``library_documents`` stays until the judgements and rule-set foreign keys move;
new reads use the shared id.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("filename", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "documents", sa.Column("content_hash", sa.Text(), server_default="", nullable=False)
    )
    op.add_column("documents", sa.Column("object_key", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.add_column(
        "documents", sa.Column("page_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "documents",
        sa.Column(
            "passages", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "tables", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "outline", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_documents_owner_user_id_users",
        "documents",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("documents", "collection_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("documents", "source_id", existing_type=sa.Uuid(), nullable=True)
    op.execute(
        """
        UPDATE documents AS document
        SET passages = library.passages,
            tables = library.tables,
            page_count = library.page_count,
            filename = library.filename,
            content_hash = library.content_hash,
            object_key = library.object_key,
            owner_user_id = COALESCE(document.owner_user_id, library.owner_user_id)
        FROM library_documents AS library
        JOIN files AS file
          ON file.tenant_id = library.tenant_id
         AND file.sha256 = library.content_hash
         AND file.deleted_at IS NULL
        WHERE document.raw_file_id = file.id
          AND document.tenant_id = library.tenant_id
          AND document.passages = '[]'::jsonb
        """
    )
    op.execute(
        """
        INSERT INTO documents (
            id, tenant_id, external_id, uri, title, mime_type, version_hash, size_bytes,
            status, filename, content_hash, object_key, owner_user_id, page_count,
            passages, tables, created_at, updated_at
        )
        SELECT
            library.id, library.tenant_id,
            'library:' || library.id::text,
            'library://' || library.id::text,
            library.title, library.media_type, library.content_hash, library.size_bytes,
            CASE WHEN library.status = 'ready' THEN 'indexed' ELSE 'failed' END,
            library.filename, library.content_hash, library.object_key, library.owner_user_id,
            library.page_count, library.passages, library.tables, library.created_at, library.updated_at
        FROM library_documents AS library
        WHERE NOT EXISTS (
            SELECT 1 FROM documents AS document
            WHERE document.id = library.id
               OR (
                    document.tenant_id = library.tenant_id
                    AND document.content_hash = library.content_hash
                    AND document.content_hash <> ''
               )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_content_hash
        ON documents (tenant_id, content_hash)
        WHERE content_hash <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_content_hash")
    op.execute("DELETE FROM documents WHERE collection_id IS NULL")
    op.alter_column("documents", "source_id", existing_type=sa.Uuid(), nullable=False)
    op.alter_column("documents", "collection_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint("fk_documents_owner_user_id_users", "documents", type_="foreignkey")
    op.drop_column("documents", "outline")
    op.drop_column("documents", "tables")
    op.drop_column("documents", "passages")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "owner_user_id")
    op.drop_column("documents", "object_key")
    op.drop_column("documents", "content_hash")
    op.drop_column("documents", "filename")
