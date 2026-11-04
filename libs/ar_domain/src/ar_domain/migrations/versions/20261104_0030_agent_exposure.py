"""Agent API keys, idempotency, grants and A2A tasks.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-04
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_api_keys",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column("secret_hash", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), server_default=sa.text("'agent'"), nullable=False),
        sa.Column("rate_limit_rpm", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column("monthly_quota", sa.Integer(), server_default=sa.text("10000"), nullable=False),
        sa.Column("month_stamp", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("month_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint("scope IN ('agent','workspace')", name="scope"),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_agent_api_keys_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_agent_api_keys_created_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_agent_api_keys_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_api_keys")),
    )
    op.create_index("ux_agent_api_keys_prefix", "agent_api_keys", ["prefix"], unique=True)
    op.create_index("ix_agent_api_keys_agent", "agent_api_keys", ["tenant_id", "agent_id"])
    op.create_table(
        "agent_api_idempotency",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), server_default=sa.text("200"), nullable=False),
        sa.Column(
            "response",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.Text(), server_default=sa.text("'completed'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("state IN ('in_flight','completed')", name="state"),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["agent_api_keys.id"],
            name=op.f("fk_agent_api_idempotency_key_id_agent_api_keys"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_agent_api_idempotency_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_api_idempotency")),
    )
    op.create_index(
        "ux_agent_api_idempotency_key",
        "agent_api_idempotency",
        ["key_id", "idempotency_key"],
        unique=True,
    )
    op.create_table(
        "agent_api_grants",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_agent_api_grants_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["agent_api_keys.id"],
            name=op.f("fk_agent_api_grants_key_id_agent_api_keys"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_agent_api_grants_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_api_grants")),
    )
    op.create_index(
        "ix_agent_api_grants_run",
        "agent_api_grants",
        ["tenant_id", "key_id", "run_id"],
    )
    op.create_table(
        "a2a_tasks",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.Text(), server_default=sa.text("'submitted'"), nullable=False),
        sa.Column("output_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "artifacts",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "state IN ('submitted','working','completed','failed','canceled','input-required')",
            name="state",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_a2a_tasks_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["agent_api_keys.id"],
            name=op.f("fk_a2a_tasks_key_id_agent_api_keys"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_a2a_tasks_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_a2a_tasks")),
    )
    op.create_index("ix_a2a_tasks_agent", "a2a_tasks", ["tenant_id", "agent_id"])
    add_updated_at_trigger("agent_api_keys")
    add_updated_at_trigger("a2a_tasks")
    for table in ("agent_api_keys", "agent_api_idempotency", "agent_api_grants", "a2a_tasks"):
        enable_tenant_rls(table)
    grant_tables(["agent_api_keys", "agent_api_idempotency", "agent_api_grants", "a2a_tasks"])


def downgrade() -> None:
    op.drop_index("ix_a2a_tasks_agent", table_name="a2a_tasks")
    op.drop_table("a2a_tasks")
    op.drop_index("ix_agent_api_grants_run", table_name="agent_api_grants")
    op.drop_table("agent_api_grants")
    op.drop_index("ux_agent_api_idempotency_key", table_name="agent_api_idempotency")
    op.drop_table("agent_api_idempotency")
    op.drop_index("ix_agent_api_keys_agent", table_name="agent_api_keys")
    op.drop_index("ux_agent_api_keys_prefix", table_name="agent_api_keys")
    op.drop_table("agent_api_keys")
