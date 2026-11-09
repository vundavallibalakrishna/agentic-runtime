"""Two-part (key id + secret) API key format.

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-09

``api_keys.key_format`` discriminates a legacy single-token ``ark_`` key (the full
token is hashed) from a two-part ``ak_<prefix>.sk_<secret>`` key (only the secret is
hashed). ``last_rotated_at`` records the most recent secret rotation. Expand only:
both columns default/allow null, so existing rows and older code keep working; RLS and
grants on ``api_keys`` are unchanged by adding nullable/defaulted columns.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "key_format",
            sa.Text(),
            server_default=sa.text("'legacy'"),
            nullable=False,
        ),
    )
    op.add_column(
        "api_keys",
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "last_rotated_at")
    op.drop_column("api_keys", "key_format")
