"""usage

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "00000000-0000-0000-0000-000000000000"
_METRICS = (
    "metric IN ('model_input_tokens','model_output_tokens','model_cached_tokens',"
    "'embedding_tokens','rerank_requests','tool_calls','sandbox_cpu_seconds',"
    "'sandbox_sessions','storage_bytes','runs')"
)


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("team_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("routine_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column("model_alias", sa.Text(), nullable=True),
        sa.Column("tool_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.CheckConstraint(_METRICS, name=op.f("ck_usage_events_metric")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_usage_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_usage_events_dedupe"),
    )
    op.create_index(
        "ix_usage_events_time", "usage_events", ["tenant_id", "occurred_at"], unique=False
    )
    op.create_table(
        "usage_daily",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), server_default=sa.text(f"'{_ZERO}'::uuid"), nullable=False),
        sa.Column("team_id", sa.UUID(), server_default=sa.text(f"'{_ZERO}'::uuid"), nullable=False),
        sa.Column(
            "agent_id", sa.UUID(), server_default=sa.text(f"'{_ZERO}'::uuid"), nullable=False
        ),
        sa.Column("model_alias", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_usage_daily_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "day",
            "metric",
            "user_id",
            "team_id",
            "agent_id",
            "model_alias",
            name=op.f("pk_usage_daily"),
        ),
    )
    op.create_table(
        "quotas",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.UUID(), nullable=True),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("limit_value", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), server_default=sa.text("'block'"), nullable=False),
        sa.Column("warn_at_pct", sa.Integer(), server_default=sa.text("80"), nullable=False),
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
            "scope_type IN ('tenant','team','user','agent')", name=op.f("ck_quotas_scope_type")
        ),
        sa.CheckConstraint(
            "metric IN ('cost_micros','model_tokens','runs','sandbox_cpu_seconds','tool_calls')",
            name=op.f("ck_quotas_metric"),
        ),
        sa.CheckConstraint("period IN ('day','month')", name=op.f("ck_quotas_period")),
        sa.CheckConstraint("limit_value >= 0", name=op.f("ck_quotas_limit_value")),
        sa.CheckConstraint("action IN ('block','warn')", name=op.f("ck_quotas_action")),
        sa.CheckConstraint("warn_at_pct BETWEEN 1 AND 100", name=op.f("ck_quotas_warn_at_pct")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_quotas_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotas")),
        sa.UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_id",
            "metric",
            "period",
            name="uq_quotas_scope",
            postgresql_nulls_not_distinct=True,
        ),
    )
    enable_tenant_rls("usage_events")
    enable_tenant_rls("usage_daily")
    add_updated_at_trigger("quotas")
    enable_tenant_rls("quotas")
    grant_tables(["usage_events", "usage_daily", "quotas"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS quotas CASCADE")
    op.execute("DROP TABLE IF EXISTS usage_daily CASCADE")
    op.execute("DROP TABLE IF EXISTS usage_events CASCADE")
