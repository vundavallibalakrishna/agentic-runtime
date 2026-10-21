"""conversations_runs

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated() -> sa.Column[object]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.Text(), server_default=sa.text("'web'"), nullable=False),
        sa.Column("title", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_preview", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rolling_summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("summary_through_message_id", sa.UUID(), nullable=True),
        sa.Column(
            "plan", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "loaded_skills",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "retention_class", sa.Text(), server_default=sa.text("'standard'"), nullable=False
        ),
        sa.Column(
            "classification", sa.Text(), server_default=sa.text("'internal'"), nullable=False
        ),
        sa.Column("active_run_id", sa.UUID(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('web','slack','teams','email','api','routine','widget','eval')",
            name=op.f("ck_conversations_channel"),
        ),
        sa.CheckConstraint("status IN ('active','archived')", name=op.f("ck_conversations_status")),
        sa.CheckConstraint(
            "retention_class IN ('standard','extended','legal_hold','ephemeral')",
            name=op.f("ck_conversations_retention_class"),
        ),
        sa.CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name=op.f("ck_conversations_classification"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_conversations_agent_id_agents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_conversations_agent_version_id_agent_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_conversations_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        "ix_conversations_user",
        "conversations",
        ["tenant_id", "user_id", sa.literal_column("last_message_at DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_conversations_agent", "conversations", ["tenant_id", "agent_id"], unique=False
    )
    op.create_index(
        "ix_conversations_title_trgm",
        "conversations",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("agent_version_id", sa.UUID(), nullable=False),
        sa.Column("parent_run_id", sa.UUID(), nullable=True),
        sa.Column("root_run_id", sa.UUID(), nullable=False),
        sa.Column("depth", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("routine_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("initiator_type", sa.Text(), nullable=False),
        sa.Column("initiator_id", sa.UUID(), nullable=True),
        sa.Column("input_message_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("temporal_workflow_id", sa.Text(), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("callback_url", sa.Text(), nullable=True),
        sa.Column(
            "notify_on_complete", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("eval_context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "usage", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("last_event_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint("depth BETWEEN 0 AND 3", name=op.f("ck_runs_depth")),
        sa.CheckConstraint(
            "trigger IN ('chat','api','channel','routine','subagent','eval')",
            name=op.f("ck_runs_trigger"),
        ),
        sa.CheckConstraint(
            "initiator_type IN ('user','service_account','routine','system')",
            name=op.f("ck_runs_initiator_type"),
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','waiting_approval','waiting_input',"
            "'completed','failed','cancelled','budget_exceeded')",
            name=op.f("ck_runs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], name=op.f("fk_runs_agent_id_agents"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_runs_agent_version_id_agent_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_runs_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"],
            ["runs.id"],
            name=op.f("fk_runs_parent_run_id_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_runs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_runs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.UniqueConstraint("temporal_workflow_id", name=op.f("uq_runs_temporal_workflow_id")),
    )
    op.create_index(
        "ix_runs_conversation",
        "runs",
        ["tenant_id", "conversation_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_runs_active",
        "runs",
        ["tenant_id", "status"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('queued','running','waiting_approval','waiting_input')"
        ),
    )
    op.create_index("ix_runs_parent", "runs", ["parent_run_id"], unique=False)
    op.create_index(
        "ix_runs_routine",
        "runs",
        ["tenant_id", "routine_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_foreign_key(
        "fk_conv_active_run",
        "conversations",
        "runs",
        ["active_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("parent_message_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'completed'"), nullable=False),
        sa.Column("is_active_branch", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("scope", sa.Text(), server_default=sa.text("'conversation'"), nullable=False),
        sa.Column("model_alias", sa.Text(), nullable=True),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("tokens_out", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "role IN ('user','assistant','tool','system')", name=op.f("ck_messages_role")
        ),
        sa.CheckConstraint(
            "status IN ('streaming','completed','failed','cancelled')",
            name=op.f("ck_messages_status"),
        ),
        sa.CheckConstraint("scope IN ('conversation','run')", name=op.f("ck_messages_scope")),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_messages_author_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.id"],
            name=op.f("fk_messages_model_id_models"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_message_id"],
            ["messages.id"],
            name=op.f("fk_messages_parent_message_id_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_messages_run_id_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_messages_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_conversation",
        "messages",
        ["tenant_id", "conversation_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_messages_run", "messages", ["run_id"], unique=False)
    op.create_index(
        "ix_messages_fts",
        "messages",
        [sa.literal_column("to_tsvector('simple', content::text)")],
        unique=False,
        postgresql_using="gin",
    )
    op.create_foreign_key(
        "fk_runs_input_msg",
        "runs",
        "messages",
        ["input_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "conversation_shares",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("principal_type", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=False),
        sa.Column("permission", sa.Text(), server_default=sa.text("'view'"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "principal_type IN ('user','group','team')",
            name=op.f("ck_conversation_shares_principal_type"),
        ),
        sa.CheckConstraint(
            "permission IN ('view')", name=op.f("ck_conversation_shares_permission")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_shares_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_conversation_shares_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_conversation_shares_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id",
            "principal_type",
            "principal_id",
            name=op.f("pk_conversation_shares"),
        ),
    )
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.Text(), nullable=False),
        sa.Column(
            "reasons",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating IN ('up','down')", name=op.f("ck_message_feedback_rating")),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_feedback_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_message_feedback_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_message_feedback_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_feedback")),
        sa.UniqueConstraint("message_id", "user_id", name="uq_message_feedback_user"),
    )
    op.create_table(
        "run_steps",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("model_alias", sa.Text(), nullable=True),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("tokens_out", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "detail", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('model_call','tool_batch','compaction','delegation','approval_wait',"
            "'memory_recall','finalize')",
            name=op.f("ck_run_steps_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','skipped','cancelled')",
            name=op.f("ck_run_steps_status"),
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.id"],
            name=op.f("fk_run_steps_model_id_models"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_steps_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_run_steps_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_steps")),
        sa.UniqueConstraint("run_id", "seq", name="uq_run_steps_seq"),
    )
    op.create_index("ix_run_steps_tenant", "run_steps", ["tenant_id", "run_id"], unique=False)
    op.create_table(
        "run_events",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_events_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_run_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "seq", name=op.f("pk_run_events")),
    )
    op.create_index("ix_run_events_tenant", "run_events", ["tenant_id", "run_id"], unique=False)
    for table in ("conversations", "runs", "messages", "run_steps"):
        add_updated_at_trigger(table)
        enable_tenant_rls(table)
    for table in ("conversation_shares", "message_feedback", "run_events"):
        enable_tenant_rls(table)
    grant_tables(
        [
            "conversations",
            "runs",
            "messages",
            "conversation_shares",
            "message_feedback",
            "run_steps",
            "run_events",
        ]
    )


def downgrade() -> None:
    for table in (
        "run_events",
        "run_steps",
        "message_feedback",
        "conversation_shares",
        "messages",
        "runs",
        "conversations",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
