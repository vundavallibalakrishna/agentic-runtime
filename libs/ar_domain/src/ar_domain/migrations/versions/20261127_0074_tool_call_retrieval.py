"""Store the passages a tool call retrieved.

Revision ID: 0074
Revises: 0073
Create Date: 2026-11-27

A run kept only how many passages a search returned. The ids, scores, query
and ranks are the retrieval record. Passage text stays out of this column.
Downgrade drops the column.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0074"
down_revision: str | None = "0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tool_calls",
        sa.Column("retrieval", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tool_calls", "retrieval")
