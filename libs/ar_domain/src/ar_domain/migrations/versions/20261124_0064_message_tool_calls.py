"""Keep the tool calls a reply shows with the reply.

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-24

A reply lists the tool calls it made: the tool, how it ended, and what it showed (a table,
a file, the agents it called). That list lived only in the memory of the process that ran
the turn. On a database-backed install the worker runs the turn and the API serves the
conversation, so a finished reply came back with its text and none of its calls, and a
reload lost every tool card.

``tool_calls`` (the table) stays the record of each call. This column is what the reply
shows: nullable, and NULL on every reply written before it.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("tool_calls", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "tool_calls")
