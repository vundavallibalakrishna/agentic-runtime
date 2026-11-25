"""Remember whether an extraction is waiting, done, or refused.

Revision ID: 0073
Revises: 0072
Create Date: 2026-11-25

The status lived only in the process that extracted the document. A restart
showed a finished review as still waiting. Downgrade drops the column.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0073"
down_revision: str | None = "0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_extractions",
        sa.Column("status", sa.Text(), server_default="done", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("document_extractions", "status")
