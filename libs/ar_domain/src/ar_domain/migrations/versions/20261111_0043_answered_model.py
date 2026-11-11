"""Remember which model wrote an assistant message.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-11

``messages.model_id`` already points at the registry row. ``answered_model`` is
the label a person sees (``Qwen3-32B``), which the turn used to keep only in
memory. Expand: the column is nullable, so a row written by the previous
release still loads.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("answered_model", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "answered_model")
