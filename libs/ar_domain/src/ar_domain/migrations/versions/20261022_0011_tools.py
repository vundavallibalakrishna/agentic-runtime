"""tools

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-22

Spliced in front of 0020 (OQ-34). ``fk_tool_calls_approval`` waits for revision 0012.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_platform_or_own_rls,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "00000000-0000-0000-0000-000000000000"
_CLASS = "classification IN ('public','internal','confidential','restricted')"


def upgrade() -> None:
    op.create_table(
        "data_connections",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("engine", sa.Text(), nullable=False),
        sa.Column("dsn_secret_ref_id", sa.UUID(), nullable=False),
        sa.Column("identity_mode", sa.Text(), server_default=sa.text("'service'"), nullable=False),
        sa.Column(
            "allowlist", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("row_limit", sa.Integer(), server_default=sa.text("1000"), nullable=False),
        sa.Column(
            "statement_timeout_s", sa.Integer(), server_default=sa.text("30"), nullable=False
        ),
        sa.Column(
            "classification", sa.Text(), server_default=sa.text("'internal'"), nullable=False
        ),
        sa.Column("schema_notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
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
            "engine IN ('postgres','mysql','mssql','oracle','snowflake','trino','clickhouse')",
            name=op.f("ck_data_connections_engine"),
        ),
        sa.CheckConstraint(
            "identity_mode IN ('service','per_user_mapped','passthrough')",
            name=op.f("ck_data_connections_identity_mode"),
        ),
        sa.CheckConstraint(
            "row_limit BETWEEN 1 AND 100000", name=op.f("ck_data_connections_row_limit")
        ),
        sa.CheckConstraint(
            "statement_timeout_s BETWEEN 1 AND 600",
            name=op.f("ck_data_connections_statement_timeout_s"),
        ),
        sa.CheckConstraint(_CLASS, name=op.f("ck_data_connections_classification")),
        sa.CheckConstraint(
            "status IN ('active','disabled')", name=op.f("ck_data_connections_status")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_data_connections_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["dsn_secret_ref_id"],
            ["secret_refs.id"],
            name=op.f("fk_data_connections_dsn_secret_ref_id_secret_refs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_data_connections_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_connections")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_data_connections_name"),
    )
    op.create_table(
        "tool_servers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("owner_team_id", sa.UUID(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint("slug ~ '^[a-z][a-z0-9_]{1,30}$'", name=op.f("ck_tool_servers_slug")),
        sa.CheckConstraint(
            "kind IN ('remote_mcp','openapi','sql','builtin','sandbox')",
            name=op.f("ck_tool_servers_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('draft','pending_review','approved','deprecated','rejected')",
            name=op.f("ck_tool_servers_status"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_team_id"],
            ["teams.id"],
            name=op.f("fk_tool_servers_owner_team_id_teams"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_tool_servers_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tool_servers_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_servers")),
    )
    op.create_index(
        "ux_tool_servers_slug",
        "tool_servers",
        [sa.literal_column(f"coalesce(tenant_id, '{_ZERO}'::uuid)"), "slug"],
        unique=True,
    )
    op.create_table(
        "tool_server_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("tool_server_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column(
            "config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("auth_mode", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.Column("secret_ref_id", sa.UUID(), nullable=True),
        sa.Column("credential_provider_id", sa.UUID(), nullable=True),
        sa.Column(
            "manifest", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("manifest_hash", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("review_status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("review_notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version ~ '^\\d+\\.\\d+\\.\\d+$'", name=op.f("ck_tool_server_versions_version")
        ),
        sa.CheckConstraint(
            "auth_mode IN ('none','static_secret','user_oauth','token_exchange','internal_jwt')",
            name=op.f("ck_tool_server_versions_auth_mode"),
        ),
        sa.CheckConstraint(
            "review_status IN ('pending','approved','rejected')",
            name=op.f("ck_tool_server_versions_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["credential_provider_id"],
            ["credential_providers.id"],
            name=op.f("fk_tool_server_versions_credential_provider_id_credential_providers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_tool_server_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_tool_server_versions_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["secret_ref_id"],
            ["secret_refs.id"],
            name=op.f("fk_tool_server_versions_secret_ref_id_secret_refs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tool_server_versions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_server_id"],
            ["tool_servers.id"],
            name=op.f("fk_tool_server_versions_tool_server_id_tool_servers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_server_versions")),
        sa.UniqueConstraint("tool_server_id", "version", name="uq_tool_server_versions"),
    )
    op.create_index(
        "ix_tsv_tenant", "tool_server_versions", ["tenant_id", "tool_server_id"], unique=False
    )
    op.create_foreign_key(
        "fk_ts_current",
        "tool_servers",
        "tool_server_versions",
        ["current_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "tools",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("tool_server_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint("name ~ '^[a-z][a-z0-9_]{0,47}$'", name=op.f("ck_tools_name")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tools_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_server_id"],
            ["tool_servers.id"],
            name=op.f("fk_tools_tool_server_id_tool_servers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tools")),
        sa.UniqueConstraint("tool_server_id", "name", name="uq_tools_name"),
    )
    op.create_index("ix_tools_tenant", "tools", ["tenant_id"], unique=False)
    op.create_table(
        "tool_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column("tool_server_version_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_hash", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=True),
        sa.Column(
            "annotations", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("risk_class", sa.Text(), nullable=False),
        sa.Column(
            "data_classification", sa.Text(), server_default=sa.text("'internal'"), nullable=False
        ),
        sa.Column(
            "required_scopes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("timeout_s", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column(
            "rate_limit_per_minute", sa.Integer(), server_default=sa.text("60"), nullable=False
        ),
        sa.Column(
            "max_result_bytes", sa.Integer(), server_default=sa.text("65536"), nullable=False
        ),
        sa.Column("idempotent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "approval_preview",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_class IN ('R0','R1','W1','W2','W3')", name=op.f("ck_tool_versions_risk_class")
        ),
        sa.CheckConstraint(
            "data_classification IN ('public','internal','confidential','restricted')",
            name=op.f("ck_tool_versions_data_classification"),
        ),
        sa.CheckConstraint("timeout_s BETWEEN 1 AND 900", name=op.f("ck_tool_versions_timeout_s")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tool_versions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"],
            ["tools.id"],
            name=op.f("fk_tool_versions_tool_id_tools"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_server_version_id"],
            ["tool_server_versions.id"],
            name=op.f("fk_tool_versions_tool_server_version_id_tool_server_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_versions")),
        sa.UniqueConstraint("tool_id", "tool_server_version_id", name="uq_tool_versions"),
    )
    op.create_index(
        "ix_tool_versions_tenant", "tool_versions", ["tenant_id", "tool_id"], unique=False
    )
    op.execute(
        "CREATE INDEX ix_tool_versions_embedding ON tool_versions "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("run_step_id", sa.UUID(), nullable=True),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("tool_id", sa.UUID(), nullable=True),
        sa.Column("tool_version_id", sa.UUID(), nullable=True),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("model_call_id", sa.Text(), nullable=False),
        sa.Column("arguments_redacted", postgresql.JSONB(), nullable=False),
        sa.Column("args_hash", sa.Text(), nullable=False),
        sa.Column("risk_class", sa.Text(), nullable=False),
        sa.Column("policy_decision", sa.Text(), nullable=True),
        sa.Column(
            "policy_reasons",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("approval_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("result_preview", sa.Text(), nullable=True),
        sa.Column("result_file_id", sa.UUID(), nullable=True),
        sa.Column("is_error", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "policy_decision IN ('allow','deny','require_approval')",
            name=op.f("ck_tool_calls_policy_decision"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','awaiting_approval','running','succeeded','failed',"
            "'denied','rejected','expired','cancelled')",
            name=op.f("ck_tool_calls_status"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_tool_calls_message_id_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["result_file_id"], ["files.id"], name="fk_tool_calls_result", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_tool_calls_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_step_id"],
            ["run_steps.id"],
            name=op.f("fk_tool_calls_run_step_id_run_steps"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tool_calls_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["tools.id"], name=op.f("fk_tool_calls_tool_id_tools"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tool_version_id"],
            ["tool_versions.id"],
            name=op.f("fk_tool_calls_tool_version_id_tool_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_tool_calls_idempotency"),
    )
    op.create_index("ix_tool_calls_run", "tool_calls", ["tenant_id", "run_id"], unique=False)
    op.create_index(
        "ix_tool_calls_tool", "tool_calls", ["tenant_id", "tool_id", "created_at"], unique=False
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_approved_tool_version_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          parent_status text;
        BEGIN
          SELECT review_status INTO parent_status
          FROM tool_server_versions WHERE id = OLD.tool_server_version_id;
          IF parent_status = 'approved' THEN
            IF TG_OP = 'DELETE' THEN
              RAISE EXCEPTION 'approved tool version is immutable';
            END IF;
            IF (to_jsonb(NEW) - 'embedding') IS DISTINCT FROM (to_jsonb(OLD) - 'embedding') THEN
              RAISE EXCEPTION 'approved tool version is immutable';
            END IF;
          END IF;
          IF TG_OP = 'DELETE' THEN
            RETURN OLD;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER tool_versions_immutable BEFORE UPDATE OR DELETE ON tool_versions "
        "FOR EACH ROW EXECUTE FUNCTION forbid_approved_tool_version_change()"
    )
    add_updated_at_trigger("data_connections")
    enable_tenant_rls("data_connections")
    enable_tenant_rls("tool_calls")
    for table in ("tool_servers", "tools"):
        add_updated_at_trigger(table)
    for table in ("tool_servers", "tool_server_versions", "tools", "tool_versions"):
        enable_platform_or_own_rls(table)
    grant_tables(
        [
            "data_connections",
            "tool_servers",
            "tool_server_versions",
            "tools",
            "tool_versions",
            "tool_calls",
        ]
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tool_versions_immutable ON tool_versions")
    op.execute("DROP FUNCTION IF EXISTS forbid_approved_tool_version_change()")
    op.execute("DROP TABLE IF EXISTS tool_calls CASCADE")
    op.execute("DROP TABLE IF EXISTS tool_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS tools CASCADE")
    op.execute("DROP TABLE IF EXISTS tool_server_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS tool_servers CASCADE")
    op.execute("DROP TABLE IF EXISTS data_connections CASCADE")
