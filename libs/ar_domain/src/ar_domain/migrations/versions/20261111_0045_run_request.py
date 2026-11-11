"""Keep what the caller asked of a turn on the run.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-11

A response format, the follow-ups switch and a child run's role were fields on the run
held in process memory. The worker loads the run from Postgres, so it never saw them and
the turn ignored the request. Expand: the column is nullable, so a run written by the
previous release still loads.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("request", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "request")
