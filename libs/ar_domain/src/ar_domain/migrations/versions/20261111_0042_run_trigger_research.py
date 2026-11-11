"""Allow the research run trigger.

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-11

Expand. ``runs.trigger`` gains ``research``. The allowed values come from
``ar_domain.conversations.triggers``, the same tuple the SQLAlchemy model uses.
Downgrade restores the list revision 0009 installed.
"""

from typing import TYPE_CHECKING

from alembic import op

from ar_domain.conversations.triggers import previous_trigger_check_sql, trigger_check_sql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_runs_trigger"), "runs", type_="check")
    op.create_check_constraint(op.f("ck_runs_trigger"), "runs", trigger_check_sql())


def downgrade() -> None:
    op.drop_constraint(op.f("ck_runs_trigger"), "runs", type_="check")
    op.create_check_constraint(op.f("ck_runs_trigger"), "runs", previous_trigger_check_sql())
