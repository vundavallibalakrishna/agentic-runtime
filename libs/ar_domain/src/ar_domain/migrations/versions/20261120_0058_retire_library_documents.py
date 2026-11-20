"""Retire ``library_documents``. Judgements and rule sets point at ``documents``.

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-20

One table holds a library extract and a knowledge document. Child rows follow
the id that survived the content-hash dedupe. Owner-only reads, and an agent
default file whose owner is set, are SQL policies. A row with no owner and no
collection is not visible.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_table,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_READ = """
CREATE POLICY document_read ON documents
AS RESTRICTIVE
FOR SELECT
USING (
  collection_id IS NOT NULL
  OR (
    owner_user_id IS NOT NULL
    AND (
      owner_user_id = app_user_id()
      OR EXISTS (
        SELECT 1
        FROM files AS file
        JOIN agents AS agent
          ON agent.tenant_id = documents.tenant_id
         AND agent.disabled_at IS NULL
         AND agent.status = 'published'
        JOIN agent_versions AS version
          ON version.id = agent.published_version_id
         AND version.tenant_id = agent.tenant_id
        WHERE file.tenant_id = documents.tenant_id
          AND file.deleted_at IS NULL
          AND file.owner_user_id IS NOT NULL
          AND (
            file.id = documents.raw_file_id
            OR (
              documents.content_hash <> ''
              AND file.sha256 = documents.content_hash
            )
          )
          AND (
            COALESCE(version.definition #> '{knowledge,fileIds}', '[]'::jsonb)
              ? file.id::text
            OR COALESCE(version.definition #> '{knowledge,file_ids}', '[]'::jsonb)
              ? file.id::text
          )
          AND (
            agent.visibility = 'tenant'
            OR agent.owner_user_id = app_user_id()
            OR (
              agent.visibility = 'team'
              AND EXISTS (
                SELECT 1
                FROM team_members AS member
                WHERE member.team_id = agent.owner_team_id
                  AND member.user_id = app_user_id()
                  AND member.tenant_id = agent.tenant_id
              )
            )
          )
      )
    )
  )
)
"""

_WRITE = """
CREATE POLICY document_insert ON documents
AS RESTRICTIVE
FOR INSERT
WITH CHECK (collection_id IS NOT NULL OR owner_user_id = app_user_id())
"""

_UPDATE = """
CREATE POLICY document_update ON documents
AS RESTRICTIVE
FOR UPDATE
USING (collection_id IS NOT NULL OR owner_user_id = app_user_id())
WITH CHECK (collection_id IS NOT NULL OR owner_user_id = app_user_id())
"""

_DELETE = """
CREATE POLICY document_delete ON documents
AS RESTRICTIVE
FOR DELETE
USING (collection_id IS NOT NULL OR owner_user_id = app_user_id())
"""

_LIBRARY_READER = """
CREATE POLICY library_reader ON library_documents
AS RESTRICTIVE
FOR ALL
USING (
  owner_user_id = app_user_id()
  OR EXISTS (
    SELECT 1
    FROM documents d
    JOIN files f ON f.id = d.raw_file_id AND f.tenant_id = d.tenant_id
    WHERE d.tenant_id = library_documents.tenant_id
      AND f.sha256 = library_documents.content_hash
      AND f.deleted_at IS NULL
      AND d.status <> 'deleted'
      AND d.acl_principals && ARRAY[
        'user:' || app_user_id()::text,
        'tenant:*'
      ]::text[]
  )
)
WITH CHECK (owner_user_id = app_user_id())
"""


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column("source_ref", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("documents", sa.Column("error_code", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_documents_source",
        "documents",
        "source IN ('', 'upload', 'workspace', 'connection')",
    )
    op.execute(
        """
        UPDATE documents
        SET source = 'upload'
        WHERE source = ''
          AND uri LIKE 'library://%'
        """
    )
    _retarget(
        "judgements",
        "document_id",
    )
    _retarget("document_checks", "document_id")
    _retarget("document_checks", "standard_document_id")
    _retarget("document_comparisons", "left_id")
    _retarget("document_comparisons", "right_id")
    _retarget("document_rewrites", "document_id")
    _retarget("rule_sets", "source_file_id")
    op.execute(
        """
        INSERT INTO documents (
            id, tenant_id, external_id, uri, title, mime_type, version_hash, size_bytes,
            status, filename, content_hash, object_key, owner_user_id, page_count,
            passages, tables, source, source_ref, error_code, metadata, error,
            created_at, updated_at
        )
        SELECT
            library.id, library.tenant_id,
            'library:' || library.id::text,
            'library://' || library.id::text,
            library.title, library.media_type, library.content_hash, library.size_bytes,
            CASE WHEN library.status = 'ready' THEN 'indexed' ELSE 'failed' END,
            library.filename, library.content_hash, library.object_key, library.owner_user_id,
            library.page_count, library.passages, library.tables,
            library.source, library.source_ref, library.error_code, library.metadata,
            library.error_message, library.created_at, library.updated_at
        FROM library_documents AS library
        WHERE NOT EXISTS (SELECT 1 FROM documents AS document WHERE document.id = library.id)
          AND NOT EXISTS (
            SELECT 1 FROM documents AS document
            WHERE document.tenant_id = library.tenant_id
              AND document.content_hash = library.content_hash
              AND library.content_hash <> ''
          )
        """
    )
    op.execute(
        """
        UPDATE rule_sets
        SET source_file_id = NULL
        WHERE source_file_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM documents AS document WHERE document.id = source_file_id)
        """
    )
    op.execute(
        """
        UPDATE document_checks
        SET standard_document_id = NULL
        WHERE standard_document_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM documents AS document WHERE document.id = standard_document_id
          )
        """
    )
    for table, column in (
        ("judgements", "document_id"),
        ("document_checks", "document_id"),
        ("document_comparisons", "left_id"),
        ("document_comparisons", "right_id"),
        ("document_rewrites", "document_id"),
    ):
        op.execute(
            f"""
            DELETE FROM {table}
            WHERE {column} IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM documents AS document WHERE document.id = {column})
            """  # noqa: S608
        )
    for name, table, _column in (
        ("fk_judgements_document_id_library_documents", "judgements", "document_id"),
        ("fk_document_checks_document_id_library_documents", "document_checks", "document_id"),
        (
            "fk_document_checks_standard_document_id_library_documents",
            "document_checks",
            "standard_document_id",
        ),
        ("fk_document_comparisons_left_id_library_documents", "document_comparisons", "left_id"),
        ("fk_document_comparisons_right_id_library_documents", "document_comparisons", "right_id"),
        ("fk_document_rewrites_document_id_library_documents", "document_rewrites", "document_id"),
        ("fk_rule_sets_source_file_id_library_documents", "rule_sets", "source_file_id"),
    ):
        op.drop_constraint(name, table, type_="foreignkey")
    op.execute("DROP POLICY IF EXISTS library_reader ON library_documents")
    op.execute("DROP TABLE library_documents")
    _point("judgements", "document_id", "CASCADE")
    _point("document_checks", "document_id", "CASCADE")
    _point("document_checks", "standard_document_id", "SET NULL")
    _point("document_comparisons", "left_id", "CASCADE")
    _point("document_comparisons", "right_id", "CASCADE")
    _point("document_rewrites", "document_id", "CASCADE")
    _point("rule_sets", "source_file_id", "SET NULL")
    op.execute(_READ)
    op.execute(_WRITE)
    op.execute(_UPDATE)
    op.execute(_DELETE)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_read ON documents")
    op.execute("DROP POLICY IF EXISTS document_insert ON documents")
    op.execute("DROP POLICY IF EXISTS document_update ON documents")
    op.execute("DROP POLICY IF EXISTS document_delete ON documents")
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
        sa.Column("object_key", sa.Text(), nullable=True),
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
            name="ck_library_documents_source",
        ),
        sa.CheckConstraint(
            "status IN ('ready','failed')",
            name="ck_library_documents_status",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_library_documents_owner_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_library_documents_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_library_documents"),
        sa.UniqueConstraint(
            "tenant_id",
            "content_hash",
            name="uq_library_documents_content_hash",
        ),
    )
    op.create_index(
        "ix_library_documents_tenant_created",
        "library_documents",
        ["tenant_id", "created_at"],
    )
    op.execute(
        """
        INSERT INTO library_documents (
            id, tenant_id, owner_user_id, title, filename, media_type, source, source_ref,
            content_hash, object_key, size_bytes, status, error_code, error_message, page_count,
            metadata, passages, tables, created_at, updated_at
        )
        SELECT
            document.id, document.tenant_id, document.owner_user_id, document.title,
            COALESCE(NULLIF(document.filename, ''), 'upload'),
            document.mime_type,
            CASE
              WHEN document.source IN ('upload', 'workspace', 'connection') THEN document.source
              ELSE 'upload'
            END,
            COALESCE(document.source_ref, ''),
            document.content_hash, document.object_key, document.size_bytes,
            CASE WHEN document.status = 'failed' THEN 'failed' ELSE 'ready' END,
            document.error_code, document.error, document.page_count,
            COALESCE(document.metadata, '{}'::jsonb),
            COALESCE(document.passages, '[]'::jsonb),
            COALESCE(document.tables, '[]'::jsonb),
            document.created_at, document.updated_at
        FROM documents AS document
        WHERE document.owner_user_id IS NOT NULL
          AND (
            document.source IN ('upload', 'workspace', 'connection')
            OR document.uri LIKE 'library://%'
          )
        """
    )
    for name, table in (
        ("fk_judgements_document_id_documents", "judgements"),
        ("fk_document_checks_document_id_documents", "document_checks"),
        ("fk_document_checks_standard_document_id_documents", "document_checks"),
        ("fk_document_comparisons_left_id_documents", "document_comparisons"),
        ("fk_document_comparisons_right_id_documents", "document_comparisons"),
        ("fk_document_rewrites_document_id_documents", "document_rewrites"),
        ("fk_rule_sets_source_file_id_documents", "rule_sets"),
    ):
        op.drop_constraint(name, table, type_="foreignkey")
    op.execute(
        """
        UPDATE rule_sets
        SET source_file_id = NULL
        WHERE source_file_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM library_documents AS library WHERE library.id = source_file_id
          )
        """
    )
    op.execute(
        """
        UPDATE document_checks
        SET standard_document_id = NULL
        WHERE standard_document_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM library_documents AS library WHERE library.id = standard_document_id
          )
        """
    )
    for table, column in (
        ("judgements", "document_id"),
        ("document_checks", "document_id"),
        ("document_comparisons", "left_id"),
        ("document_comparisons", "right_id"),
        ("document_rewrites", "document_id"),
    ):
        op.execute(
            f"""
            DELETE FROM {table}
            WHERE NOT EXISTS (
              SELECT 1 FROM library_documents AS library WHERE library.id = {table}.{column}
            )
            """  # noqa: S608
        )
    _restore("judgements", "document_id", "CASCADE")
    _restore("document_checks", "document_id", "CASCADE")
    _restore("document_checks", "standard_document_id", "SET NULL")
    _restore("document_comparisons", "left_id", "CASCADE")
    _restore("document_comparisons", "right_id", "CASCADE")
    _restore("document_rewrites", "document_id", "CASCADE")
    _restore("rule_sets", "source_file_id", "SET NULL")
    add_updated_at_trigger("library_documents")
    enable_tenant_rls("library_documents")
    grant_table("library_documents")
    op.execute(_LIBRARY_READER)
    op.drop_constraint("ck_documents_source", "documents", type_="check")
    op.drop_column("documents", "metadata")
    op.drop_column("documents", "error_code")
    op.drop_column("documents", "source_ref")
    op.drop_column("documents", "source")


def _retarget(table: str, column: str) -> None:
    op.execute(
        f"""
        UPDATE {table} AS child
        SET {column} = document.id
        FROM library_documents AS library
        JOIN documents AS document
          ON document.tenant_id = library.tenant_id
         AND document.content_hash = library.content_hash
         AND library.content_hash <> ''
        WHERE child.{column} = library.id
          AND NOT EXISTS (SELECT 1 FROM documents AS existing WHERE existing.id = library.id)
        """  # noqa: S608
    )


def _point(table: str, column: str, ondelete: str) -> None:
    op.create_foreign_key(
        f"fk_{table}_{column}_documents",
        table,
        "documents",
        [column],
        ["id"],
        ondelete=ondelete,
    )


def _restore(table: str, column: str, ondelete: str) -> None:
    op.create_foreign_key(
        f"fk_{table}_{column}_library_documents",
        table,
        "library_documents",
        [column],
        ["id"],
        ondelete=ondelete,
    )
