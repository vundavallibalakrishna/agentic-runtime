"""Owner-only library reads, and one durable file per hash.

Revision ID: 0055
Revises: 0054
Create Date: 2026-11-20

A library row is visible to its owner. A reader of a collection that holds the
same bytes can also see it. A durable file (no retention, not deleted) is unique
on (tenant_id, sha256), so uploading the same bytes again returns the same id.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY = """
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
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_files_durable_sha
        ON files (tenant_id, sha256)
        WHERE deleted_at IS NULL
          AND retention_until IS NULL
          AND sha256 IS NOT NULL
        """
    )
    op.execute(_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS library_reader ON library_documents")
    op.execute("DROP INDEX IF EXISTS uq_files_durable_sha")
