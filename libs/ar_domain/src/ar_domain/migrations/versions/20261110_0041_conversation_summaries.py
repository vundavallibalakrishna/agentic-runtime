"""Conversation summaries live in Postgres so a second replica can read them.

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-10

Expand. The summary is one row per conversation. Downgrade drops the table.
The conversation's own rolling_summary column stays.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("through_message_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_conversation_summaries_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_summaries_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_summaries")),
        sa.UniqueConstraint(
            "conversation_id", name=op.f("uq_conversation_summaries_conversation_id")
        ),
    )
    add_updated_at_trigger("conversation_summaries")
    enable_tenant_rls("conversation_summaries")
    grant_tables(["conversation_summaries"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_summaries")
