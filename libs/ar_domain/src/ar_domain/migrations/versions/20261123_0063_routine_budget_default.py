"""Give routines that still hold the old default budget the run default.

Revision ID: 0063
Revises: 0062
Create Date: 2026-11-23

A routine's budget was stored and shown but never applied: a routine ran on its agent's
budget alone. It is now applied as a ceiling under the agent's. The default a routine
was created with (8 steps, 4 tool calls, 8,000 tokens, 300 seconds) was never meant to
bind and would stop most runs, so every routine that still holds exactly that default,
or an empty budget, is given the run default, which adds no limit of its own. A budget a
person set is left as it is and now takes effect.

Data only. Downgrade puts the old default back on the rows that hold the new one.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Both budgets as they were when this revision was written. A migration keeps its own copy.
_OLD = (
    '{"max_steps": 8, "max_tokens": 8000, "max_cost_micros": 0, "max_wall_clock_s": 300, '
    '"max_tool_calls": 4, "max_parallel_tool_calls": 1}'
)
_NEW = (
    '{"max_steps": 16, "max_tokens": 80000, "max_cost_micros": 4000000, '
    '"max_wall_clock_s": 600, "max_tool_calls": 16, "max_parallel_tool_calls": 1}'
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE routines SET budget = CAST(:new AS jsonb) "
            "WHERE budget = CAST(:old AS jsonb) OR budget = '{}'::jsonb"
        ).bindparams(new=_NEW, old=_OLD)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE routines SET budget = CAST(:old AS jsonb) WHERE budget = CAST(:new AS jsonb)"
        ).bindparams(new=_NEW, old=_OLD)
    )
