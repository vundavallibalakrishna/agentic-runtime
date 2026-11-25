"""A webhook secret lives in the named secret, not a second reference row.

Revision ID: 0070
Revises: 0069
Create Date: 2026-11-25

``secret_ref_id`` may be empty. Downgrade refuses while a webhook has no
reference, and does not delete the webhook.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("outbound_webhooks", "secret_ref_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(
        sa.text("SELECT count(*) FROM outbound_webhooks WHERE secret_ref_id IS NULL")
    ).scalar()
    if count:
        raise RuntimeError("cannot restore a required secret reference while one is empty")
    op.alter_column("outbound_webhooks", "secret_ref_id", existing_type=sa.UUID(), nullable=False)
