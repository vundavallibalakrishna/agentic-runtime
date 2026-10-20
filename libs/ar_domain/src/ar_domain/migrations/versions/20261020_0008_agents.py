"""agents

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("avatar_file_id", sa.UUID(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("owner_team_id", sa.UUID(), nullable=True),
        sa.Column("visibility", sa.Text(), server_default=sa.text("'private'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("risk_tier", sa.Text(), server_default=sa.text("'low'"), nullable=False),
        sa.Column("draft_version_id", sa.UUID(), nullable=True),
        sa.Column("published_version_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name=op.f("ck_agents_slug")),
        sa.CheckConstraint(
            "visibility IN ('private','team','tenant')", name=op.f("ck_agents_visibility")
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','archived')", name=op.f("ck_agents_status")
        ),
        sa.CheckConstraint(
            "risk_tier IN ('low','medium','high')", name=op.f("ck_agents_risk_tier")
        ),
        sa.ForeignKeyConstraint(
            ["owner_team_id"],
            ["teams.id"],
            name=op.f("fk_agents_owner_team_id_teams"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_agents_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_agents_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_agents_slug"),
    )
    op.create_index("ix_agents_tenant_status", "agents", ["tenant_id", "status"], unique=False)
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("definition_hash", sa.Text(), nullable=False),
        sa.Column("change_note", sa.Text(), server_default=sa.text("''"), nullable=False),
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
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "state IN ('draft','published','superseded')", name=op.f("ck_agent_versions_state")
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_agent_versions_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_agent_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["users.id"],
            name=op.f("fk_agent_versions_published_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_agent_versions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_versions")),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_version"),
    )
    op.create_index(
        "ix_agent_versions_tenant", "agent_versions", ["tenant_id", "agent_id"], unique=False
    )
    op.create_foreign_key(
        "fk_agents_draft",
        "agents",
        "agent_versions",
        ["draft_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_agents_published",
        "agents",
        "agent_versions",
        ["published_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "agent_version_bindings",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "target_id",
            sa.UUID(),
            server_default=sa.text(f"'{_ZERO}'::uuid"),
            nullable=False,
        ),
        sa.Column("target_key", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('tool','tool_server','knowledge_collection','skill','subagent',"
            "'sandbox_template','model_alias')",
            name=op.f("ck_agent_version_bindings_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_agent_version_bindings_agent_version_id_agent_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_agent_version_bindings_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "agent_version_id",
            "kind",
            "target_id",
            "target_key",
            name=op.f("pk_agent_version_bindings"),
        ),
    )
    op.create_index(
        "ix_avb_target",
        "agent_version_bindings",
        ["tenant_id", "kind", "target_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION forbid_published_agent_version_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.state = 'published' THEN
            RAISE EXCEPTION 'published agent versions are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER published_immutable BEFORE UPDATE ON agent_versions "
        "FOR EACH ROW EXECUTE FUNCTION forbid_published_agent_version_update()"
    )
    for table in ("agents", "agent_versions"):
        add_updated_at_trigger(table)
        enable_tenant_rls(table)
    enable_tenant_rls("agent_version_bindings")
    grant_tables(["agents", "agent_versions", "agent_version_bindings"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_version_bindings CASCADE")
    op.execute("DROP TRIGGER IF EXISTS published_immutable ON agent_versions")
    op.execute("DROP FUNCTION IF EXISTS forbid_published_agent_version_update()")
    op.execute("DROP TABLE IF EXISTS agent_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS agents CASCADE")
