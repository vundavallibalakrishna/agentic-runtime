"""conversation model alias

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-28 18:00:00
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("model_alias", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "model_alias")
