"""Keep one file per content for uploads only, not for what agents write.

Revision ID: 0060
Revises: 0059
Create Date: 2026-11-20

Revision 0055 made a tenant's durable files unique by their content hash, so a file
uploaded twice keeps one row. The index covered every kind of file. A file an agent
writes is a row of its own in its conversation, and two of them often hold the same
bytes: the same report made twice, the same note saved in two conversations. The second
one could not be saved, and the tool call that made it ended in an internal error.

The index now covers uploads alone. Data is not changed. Downgrade puts the wider index
back, which fails if two files an agent wrote already share their bytes; delete or
expire one of them first.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHERE = "deleted_at IS NULL AND retention_until IS NULL AND sha256 IS NOT NULL"


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_files_durable_sha")
    op.execute(
        "CREATE UNIQUE INDEX uq_files_durable_sha ON files (tenant_id, sha256) "
        f"WHERE {_WHERE} AND kind = 'upload'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_files_durable_sha")
    op.execute(
        f"CREATE UNIQUE INDEX uq_files_durable_sha ON files (tenant_id, sha256) WHERE {_WHERE}"
    )
