"""Indexes for caller-owned keyset pages; no row or contract is removed.

Revision ID: 0075
Revises: 0074
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0075"
down_revision: str | None = "0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support bounded caller-owned list reads in stable timestamp/id order."""
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY ix_conversations_caller_page ON conversations "
            "(tenant_id, user_id, updated_at DESC, id DESC) WHERE deleted_at IS NULL"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY ix_runs_caller_page ON runs "
            "(tenant_id, user_id, created_at DESC, id DESC)"
        )


def downgrade() -> None:
    """Remove only the added indexes; tenant rows and RLS remain intact."""
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY ix_runs_caller_page")
        op.execute("DROP INDEX CONCURRENTLY ix_conversations_caller_page")
