"""sandboxes

Revision ID: 0013
Revises: 0022
Create Date: 2026-10-22

Tables of schema §10 plus ``fk_sandboxes_snapshot``. The revision id stays 0013,
the number reserved for this milestone. It follows 0022, the current head.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_platform_or_own_rls,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0013"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    op.create_table(
        "sandbox_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("image_ref", sa.Text(), nullable=False),
        sa.Column("runtime_class", sa.Text(), server_default=sa.text("'gvisor'"), nullable=False),
        sa.Column("cpu_millis", sa.Integer(), server_default=sa.text("2000"), nullable=False),
        sa.Column("memory_mb", sa.Integer(), server_default=sa.text("4096"), nullable=False),
        sa.Column("disk_gb", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("allow_browser", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("allow_packages", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "egress_allowlist",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "max_classification",
            sa.Text(),
            server_default=sa.text("'confidential'"),
            nullable=False,
        ),
        sa.Column("idle_suspend_s", sa.Integer(), server_default=sa.text("900"), nullable=False),
        sa.Column("max_lifetime_s", sa.Integer(), server_default=sa.text("86400"), nullable=False),
        sa.Column("exec_timeout_s", sa.Integer(), server_default=sa.text("120"), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default=sa.text("7"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
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
            "runtime_class IN ('gvisor','kata','runc_dev')",
            name=op.f("ck_sandbox_templates_runtime_class"),
        ),
        sa.CheckConstraint(
            "max_classification IN ('public','internal','confidential','restricted')",
            name=op.f("ck_sandbox_templates_max_classification"),
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled')",
            name=op.f("ck_sandbox_templates_status"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_sandbox_templates_slug",
        "sandbox_templates",
        [sa.literal_column(f"coalesce(tenant_id, '{_ZERO}'::uuid)"), "slug"],
        unique=True,
    )
    op.create_table(
        "sandboxes",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("driver", sa.Text(), nullable=False),
        sa.Column("driver_ref", sa.Text(), nullable=True),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("auth_token_hash", sa.Text(), nullable=True),
        sa.Column("workspace_volume", sa.Text(), nullable=True),
        sa.Column("snapshot_file_id", sa.UUID(), nullable=True),
        sa.Column("cpu_seconds", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
            "scope IN ('conversation','agent_user','agent')",
            name=op.f("ck_sandboxes_scope"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','starting','ready','suspending','suspended','resuming',"
            "'terminating','terminated','failed')",
            name=op.f("ck_sandboxes_status"),
        ),
        sa.CheckConstraint("driver IN ('docker','kubernetes')", name=op.f("ck_sandboxes_driver")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["snapshot_file_id"],
            ["files.id"],
            name="fk_sandboxes_snapshot",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["template_id"], ["sandbox_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_sandboxes_live_scope",
        "sandboxes",
        ["tenant_id", "scope_key"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('terminated','failed')"),
    )
    op.create_index("ix_sandboxes_idle", "sandboxes", ["status", "last_active_at"])
    add_updated_at_trigger("sandbox_templates")
    add_updated_at_trigger("sandboxes")
    enable_platform_or_own_rls("sandbox_templates")
    enable_tenant_rls("sandboxes")
    grant_tables(["sandbox_templates", "sandboxes"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sandboxes CASCADE")
    op.execute("DROP TABLE IF EXISTS sandbox_templates CASCADE")
