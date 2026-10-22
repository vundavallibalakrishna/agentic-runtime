"""policy_approvals

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-22

Tables of schema §7. ``fk_tool_calls_approval`` closes the cycle opened in 0011.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_append_only_trigger,
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'rules'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("active_version_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint("kind IN ('rules','rego')", name=op.f("ck_policies_kind")),
        sa.CheckConstraint(
            "status IN ('draft','active','disabled')", name=op.f("ck_policies_status")
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_policies_name"),
    )
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=True),
        sa.Column("rego", sa.Text(), nullable=True),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column(
            "test_report",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(document IS NOT NULL) <> (rego IS NOT NULL)",
            name=op.f("ck_policy_versions_document_xor_rego"),
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", "version", name="uq_policy_versions_version"),
    )
    op.create_foreign_key(
        "fk_policies_active",
        "policies",
        "policy_versions",
        ["active_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tool_call_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("requested_for_user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("risk_class", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("args_hash", sa.Text(), nullable=False),
        sa.Column(
            "arguments", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "preview", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("justification", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "approver_rule",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("required_approvals", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "step_up_required", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "policy_reasons",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending','approved','rejected','expired','cancelled')",
            name=op.f("ck_approvals_status"),
        ),
        sa.CheckConstraint(
            "required_approvals BETWEEN 1 AND 5",
            name=op.f("ck_approvals_required_approvals"),
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_for_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_call_id"], ["tool_calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_call_id", name="uq_approvals_tool_call_id"),
    )
    op.create_index(
        "ix_approvals_pending",
        "approvals",
        ["tenant_id", "status", "expires_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_approvals_run", "approvals", ["run_id"], unique=False)
    op.create_foreign_key(
        "fk_tool_calls_approval",
        "tool_calls",
        "approvals",
        ["approval_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("approval_id", sa.UUID(), nullable=False),
        sa.Column("approver_user_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("args_hash", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "step_up_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('approve','reject')", name=op.f("ck_approval_decisions_decision")
        ),
        sa.CheckConstraint(
            "channel IN ('web','slack','teams','email','api')",
            name=op.f("ck_approval_decisions_channel"),
        ),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "approval_id", "approver_user_id", name="uq_approval_decisions_approver"
        ),
    )
    op.create_table(
        "standing_approvals",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("routine_id", sa.UUID(), nullable=True),
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column(
            "argument_constraints",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_id IS NOT NULL OR routine_id IS NOT NULL",
            name=op.f("ck_standing_approvals_target"),
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_standing_approvals_lookup",
        "standing_approvals",
        ["tenant_id", "tool_id"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    for table in ("policies", "approvals"):
        add_updated_at_trigger(table)
        enable_tenant_rls(table)
    add_append_only_trigger("policy_versions")
    for table in ("policy_versions", "approval_decisions", "standing_approvals"):
        enable_tenant_rls(table)
    grant_tables(
        [
            "policies",
            "policy_versions",
            "approvals",
            "approval_decisions",
            "standing_approvals",
        ],
        append_only=["policy_versions"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tool_calls_approval", "tool_calls", type_="foreignkey")
    op.drop_index("ix_standing_approvals_lookup", table_name="standing_approvals")
    op.drop_table("standing_approvals")
    op.drop_table("approval_decisions")
    op.drop_index("ix_approvals_run", table_name="approvals")
    op.drop_index("ix_approvals_pending", table_name="approvals")
    op.drop_table("approvals")
    op.drop_constraint("fk_policies_active", "policies", type_="foreignkey")
    op.drop_table("policy_versions")
    op.drop_table("policies")
