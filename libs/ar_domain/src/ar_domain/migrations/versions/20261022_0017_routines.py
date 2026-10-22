"""routines

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-22 12:10:00.000000
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "routines",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("run_as", sa.Text(), server_default=sa.text("'owner'"), nullable=False),
        sa.Column("service_account_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("trigger_config", postgresql.JSONB(), nullable=False),
        sa.Column("event_filter", sa.Text(), nullable=True),
        sa.Column(
            "delivery",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("max_runs_per_day", sa.Integer(), server_default=sa.text("48"), nullable=False),
        sa.Column(
            "concurrency_policy", sa.Text(), server_default=sa.text("'skip'"), nullable=False
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("paused_reason", sa.Text(), nullable=True),
        sa.Column("temporal_schedule_id", sa.Text(), nullable=True),
        sa.Column("webhook_path_token", sa.Text(), nullable=True),
        sa.Column("webhook_secret_ref_id", sa.UUID(), nullable=True),
        sa.Column(
            "consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
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
            "run_as IN ('owner','service_account')", name=op.f("ck_routines_run_as")
        ),
        sa.CheckConstraint(
            "run_as = 'owner' OR service_account_id IS NOT NULL",
            name=op.f("ck_routines_service_account"),
        ),
        sa.CheckConstraint(
            "length(instructions) <= 20000", name=op.f("ck_routines_instructions_len")
        ),
        sa.CheckConstraint(
            "trigger_type IN ('schedule','webhook','channel_event','email',"
            "'file_arrival','db_change','manual')",
            name=op.f("ck_routines_trigger_type"),
        ),
        sa.CheckConstraint(
            "max_runs_per_day BETWEEN 1 AND 10000", name=op.f("ck_routines_max_runs")
        ),
        sa.CheckConstraint(
            "concurrency_policy IN ('skip','buffer_one','allow')",
            name=op.f("ck_routines_concurrency"),
        ),
        sa.CheckConstraint(
            "status IN ('active','paused','needs_review','disabled')",
            name=op.f("ck_routines_status"),
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["service_account_id"], ["service_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["webhook_secret_ref_id"], ["secret_refs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("webhook_path_token", name="uq_routines_webhook_token"),
    )
    op.create_index("ix_routines_tenant", "routines", ["tenant_id", "status"])
    op.create_index("ix_routines_owner", "routines", ["tenant_id", "owner_user_id"])
    op.create_table(
        "routine_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("routine_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("envelope", postgresql.JSONB(), nullable=False),
        sa.Column("payload_file_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('schedule','webhook','slack','teams','email','s3','db','manual')",
            name=op.f("ck_routine_events_source"),
        ),
        sa.CheckConstraint(
            "status IN ('accepted','duplicate','filtered','rate_limited',"
            "'skipped_concurrency','started','failed')",
            name=op.f("ck_routine_events_status"),
        ),
        sa.ForeignKeyConstraint(["payload_file_id"], ["files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["routine_id"], ["routines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("routine_id", "idempotency_key", name="uq_routine_events_idempotency"),
    )
    op.create_index(
        "ix_routine_events_routine",
        "routine_events",
        ["tenant_id", "routine_id", sa.literal_column("received_at DESC")],
    )
    op.create_foreign_key(
        "fk_runs_routine", "runs", "routines", ["routine_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_sa_routine",
        "standing_approvals",
        "routines",
        ["routine_id"],
        ["id"],
        ondelete="CASCADE",
    )
    enable_tenant_rls("routines")
    enable_tenant_rls("routine_events")
    add_updated_at_trigger("routines")
    grant_tables(["routines", "routine_events"])


def downgrade() -> None:
    op.drop_constraint("fk_sa_routine", "standing_approvals", type_="foreignkey")
    op.drop_constraint("fk_runs_routine", "runs", type_="foreignkey")
    op.drop_index("ix_routine_events_routine", table_name="routine_events")
    op.drop_table("routine_events")
    op.drop_index("ix_routines_owner", table_name="routines")
    op.drop_index("ix_routines_tenant", table_name="routines")
    op.drop_table("routines")
