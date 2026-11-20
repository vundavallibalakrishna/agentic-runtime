"""Keep what an eval run was asked to do: its tags and whether every tool is replaced.

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-20

An eval run kept its tags and its ``mock_all_tools`` choice in the process that started
it. The worker that carries the run out reads the row from the database, where neither
was stored, so a run limited to some tags ran every case and a run that asked for every
tool to be replaced called the real ones. The agent the run is for was not stored
either, and is now read through the version the run names, which was.

Expand only: two columns with defaults. Downgrade drops them.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eval_runs",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "eval_runs",
        sa.Column("mock_all_tools", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("eval_runs", "mock_all_tools")
    op.drop_column("eval_runs", "tags")
