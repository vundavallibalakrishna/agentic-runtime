"""Owner-only library reads, and one durable file per hash.

Revision ID: 0055
Revises: 0054
Create Date: 2026-11-20

A library row is visible to its owner. A reader of a collection that holds the
same bytes can also see it. A durable file (no retention, not deleted) is unique
on (tenant_id, sha256), so uploading the same bytes again returns the same id.

``library_documents`` has no ``created_by``, and ``files`` has no ``created_by``.
The uploader is ``files.owner_user_id``. A row whose owner is missing takes that
uploader when a file in the tenant has the same hash, otherwise the tenant admin
(the user assigned role ``tenant_admin``), otherwise the earliest user in the
tenant. The column is then NOT NULL. It was created NOT NULL in 0026; this
revision states the rule for any row that arrived without an owner.
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
    op.execute(
        """
        UPDATE library_documents AS document
        SET owner_user_id = picked.owner_user_id
        FROM (
          SELECT DISTINCT ON (file.tenant_id, file.sha256)
            file.tenant_id, file.sha256, file.owner_user_id
          FROM files AS file
          WHERE file.owner_user_id IS NOT NULL
            AND file.deleted_at IS NULL
            AND file.sha256 IS NOT NULL
          ORDER BY file.tenant_id, file.sha256, file.created_at
        ) AS picked
        WHERE document.owner_user_id IS NULL
          AND document.tenant_id = picked.tenant_id
          AND document.content_hash = picked.sha256
        """
    )
    op.execute(
        """
        UPDATE library_documents AS document
        SET owner_user_id = admin.user_id
        FROM (
          SELECT DISTINCT ON (usr.tenant_id) usr.tenant_id, usr.id AS user_id
          FROM users AS usr
          LEFT JOIN role_assignments AS assignment
            ON assignment.tenant_id = usr.tenant_id
           AND assignment.principal_type = 'user'
           AND assignment.principal_id = usr.id
          LEFT JOIN roles AS role
            ON role.id = assignment.role_id
           AND role.key = 'tenant_admin'
          ORDER BY usr.tenant_id, (role.id IS NULL), usr.created_at
        ) AS admin
        WHERE document.owner_user_id IS NULL
          AND document.tenant_id = admin.tenant_id
        """
    )
    op.execute("ALTER TABLE library_documents ALTER COLUMN owner_user_id SET NOT NULL")
    op.execute(_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS library_reader ON library_documents")
    op.execute("DROP INDEX IF EXISTS uq_files_durable_sha")
