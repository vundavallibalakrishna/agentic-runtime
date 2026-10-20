"""audit_events

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_append_only_trigger,
    enable_audit_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("tenant_seq", sa.BigInteger(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("on_behalf_of_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("tool_call_id", sa.UUID(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), server_default=sa.text("'success'"), nullable=False),
        sa.Column("data_classification", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user','service_account','agent','system','platform_admin')",
            name=op.f("ck_audit_events_actor_type"),
        ),
        sa.CheckConstraint(
            "outcome IN ('success','failure')", name=op.f("ck_audit_events_outcome")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_audit_events_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
        sa.UniqueConstraint(
            "tenant_id",
            "tenant_seq",
            name="uq_audit_events_seq",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_audit_action",
        "audit_events",
        ["tenant_id", "action", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_actor",
        "audit_events",
        ["tenant_id", "actor_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_tenant_time",
        "audit_events",
        ["tenant_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    enable_audit_rls("audit_events")

    add_append_only_trigger("audit_events")
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM ar_app")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION purge_audit_events(p_tenant uuid, p_before timestamptz)
        RETURNS bigint
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
          removed bigint;
        BEGIN
          IF p_before > now() - interval '1 year' THEN
            RAISE EXCEPTION 'audit retention window is too recent';
          END IF;
          PERFORM set_config('session_replication_role', 'replica', true);
          DELETE FROM audit_events WHERE tenant_id = p_tenant AND occurred_at < p_before;
          GET DIAGNOSTICS removed = ROW_COUNT;
          RETURN removed;
        END $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION purge_audit_events(uuid, timestamptz) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION purge_audit_events(uuid, timestamptz) TO ar_platform")
    grant_tables(["audit_events"], append_only=["audit_events"])


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS purge_audit_events(uuid, timestamptz)")
    op.execute("DROP TABLE IF EXISTS audit_events CASCADE")
