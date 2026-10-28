"""evals

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-28 00:00:00.000000
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_suites",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'functional'"), nullable=False),
        sa.Column(
            "gate", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
            "kind IN ('functional','retrieval','safety','red_team')",
            name=op.f("ck_eval_suites_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_eval_suites_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_eval_suites_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_eval_suites_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_suites")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_eval_suites_name"),
    )
    op.create_table(
        "eval_cases",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("suite_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column("assertions", postgresql.JSONB(), nullable=False),
        sa.Column(
            "tool_mocks", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
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
        sa.ForeignKeyConstraint(
            ["suite_id"],
            ["eval_suites.id"],
            name=op.f("fk_eval_cases_suite_id_eval_suites"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_eval_cases_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_cases")),
    )
    op.create_index("ix_eval_cases_suite", "eval_cases", ["tenant_id", "suite_id"], unique=False)
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("suite_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=True),
        sa.Column("model_alias_override", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column(
            "summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("baseline_eval_run_id", sa.UUID(), nullable=True),
        sa.Column("temporal_workflow_id", sa.Text(), nullable=False),
        sa.Column("triggered_by", sa.UUID(), nullable=True),
        sa.Column("trigger", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name=op.f("ck_eval_runs_status"),
        ),
        sa.CheckConstraint(
            "trigger IN ('manual','publish_gate','schedule','ci')",
            name=op.f("ck_eval_runs_trigger"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_eval_runs_agent_version_id_agent_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["baseline_eval_run_id"],
            ["eval_runs.id"],
            name=op.f("fk_eval_runs_baseline_eval_run_id_eval_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["suite_id"],
            ["eval_suites.id"],
            name=op.f("fk_eval_runs_suite_id_eval_suites"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_eval_runs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"],
            ["users.id"],
            name=op.f("fk_eval_runs_triggered_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_runs")),
    )
    op.create_index(
        "ix_eval_runs_suite",
        "eval_runs",
        ["tenant_id", "suite_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "eval_results",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("eval_run_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column(
            "scores", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("output_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_micros", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["eval_cases.id"],
            name=op.f("fk_eval_results_case_id_eval_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["eval_run_id"],
            ["eval_runs.id"],
            name=op.f("fk_eval_results_eval_run_id_eval_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_eval_results_run_id_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_eval_results_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_results")),
        sa.UniqueConstraint("eval_run_id", "case_id", name="uq_eval_results_case"),
    )
    for table in ("eval_suites", "eval_cases"):
        add_updated_at_trigger(table)
    for table in ("eval_suites", "eval_cases", "eval_runs", "eval_results"):
        enable_tenant_rls(table)
    grant_tables(["eval_suites", "eval_cases", "eval_runs", "eval_results"])


def downgrade() -> None:
    for table in ("eval_results", "eval_runs", "eval_cases", "eval_suites"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
