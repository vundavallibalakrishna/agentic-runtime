"""Per-model request options.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-05

``models.request_options`` holds provider-specific chat-completion parameters that
are merged into every request for that model (for example a chat template switch).
Expand only: the column has a default, so older code keeps working.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column(
            "request_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("models", "request_options")
