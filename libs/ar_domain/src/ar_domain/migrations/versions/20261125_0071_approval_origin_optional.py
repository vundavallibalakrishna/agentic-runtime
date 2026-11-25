"""A review can be stored without a run, an agent, or a tool call.

Revision ID: 0071
Revises: 0070
Create Date: 2026-11-25

An extraction review is opened by the library, which has a run and an agent
when a tool called it and neither when a person extracts from the library.
The row is stored either way. Downgrade refuses while any of those ids is empty.

A webhook redelivery is a new attempt row for the same outbox event, so the
unique pair of webhook and event is dropped. Receivers de-duplicate on the event id.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("run_id", "agent_id", "tool_call_id")


def upgrade() -> None:
    for name in _COLUMNS:
        op.alter_column("approvals", name, existing_type=sa.UUID(), nullable=True)
    op.drop_constraint("uq_webhook_delivery_event", "webhook_deliveries", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    empty = bind.execute(
        sa.text(
            "SELECT count(*) FROM approvals "
            "WHERE run_id IS NULL OR agent_id IS NULL OR tool_call_id IS NULL"
        )
    ).scalar()
    if empty:
        raise RuntimeError("cannot restore required approval ids while one is empty")
    for name in _COLUMNS:
        op.alter_column("approvals", name, existing_type=sa.UUID(), nullable=False)
    op.create_unique_constraint(
        "uq_webhook_delivery_event", "webhook_deliveries", ["webhook_id", "outbox_event_id"]
    )
