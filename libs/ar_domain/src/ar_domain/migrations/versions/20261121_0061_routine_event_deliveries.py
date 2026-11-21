"""Keep what happened to each delivery of a routine event.

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-21

A routine event kept its delivery results (sent, failed and why, waiting for its owner)
in the process that completed it. The worker that sends a delivery after its owner
approves it, and the screen that lists a routine's events, read the row from the
database, where the results were not stored: a failed delivery left no reason anyone
could read, and an approved one could not be matched to the event it belongs to.

Expand only: one column with a default. Downgrade drops it.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "routine_events",
        sa.Column(
            "detail",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("routine_events", "detail")
