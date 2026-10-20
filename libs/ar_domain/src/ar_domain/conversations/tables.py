"""Conversation and run tables. Spec: docs/04-data/schema.md §5."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, text_array, updated_at_col, uuid_pk


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('web','slack','teams','email','api','routine','widget','eval')",
            name="channel",
        ),
        CheckConstraint("status IN ('active','archived')", name="status"),
        CheckConstraint(
            "retention_class IN ('standard','extended','legal_hold','ephemeral')",
            name="retention_class",
        ),
        CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name="classification",
        ),
        Index(
            "ix_conversations_user",
            "tenant_id",
            "user_id",
            text("last_message_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_conversations_agent", "tenant_id", "agent_id"),
        Index(
            "ix_conversations_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'web'"))
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    rolling_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    summary_through_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    plan: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    loaded_skills: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    retention_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'standard'")
    )
    classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'internal'")
    )
    active_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", name="fk_conv_active_run", ondelete="SET NULL", use_alter=True),
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationShare(Base):
    __tablename__ = "conversation_shares"
    __table_args__ = (
        CheckConstraint("principal_type IN ('user','group','team')", name="principal_type"),
        CheckConstraint("permission IN ('view')", name="permission"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    principal_type: Mapped[str] = mapped_column(Text, primary_key=True)
    principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    permission: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'view'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("depth BETWEEN 0 AND 3", name="depth"),
        CheckConstraint(
            "trigger IN ('chat','api','channel','routine','subagent','eval')",
            name="trigger",
        ),
        CheckConstraint(
            "initiator_type IN ('user','service_account','routine','system')",
            name="initiator_type",
        ),
        CheckConstraint(
            "status IN ('queued','running','waiting_approval','waiting_input',"
            "'completed','failed','cancelled','budget_exceeded')",
            name="status",
        ),
        Index("ix_runs_conversation", "tenant_id", "conversation_id", text("created_at DESC")),
        Index(
            "ix_runs_active",
            "tenant_id",
            "status",
            postgresql_where=text(
                "status IN ('queued','running','waiting_approval','waiting_input')"
            ),
        ),
        Index("ix_runs_parent", "parent_run_id"),
        Index("ix_runs_routine", "tenant_id", "routine_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="RESTRICT"), nullable=False
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE")
    )
    root_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    routine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    initiator_type: Mapped[str] = mapped_column(Text, nullable=False)
    initiator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    input_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", name="fk_runs_input_msg", ondelete="SET NULL", use_alter=True),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    temporal_workflow_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    budget: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Text)
    notify_on_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    eval_context: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, object]] = jsonb_col()
    result_summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    trace_id: Mapped[str | None] = mapped_column(Text)
    last_event_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','tool','system')", name="role"),
        CheckConstraint(
            "status IN ('streaming','completed','failed','cancelled')",
            name="status",
        ),
        CheckConstraint("scope IN ('conversation','run')", name="scope"),
        Index("ix_messages_conversation", "tenant_id", "conversation_id", "created_at"),
        Index("ix_messages_run", "run_id"),
        Index(
            "ix_messages_fts",
            text("to_tsvector('simple', content::text)"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL")
    )
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'completed'"))
    is_active_branch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'conversation'"))
    model_alias: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL")
    )
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    external_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class MessageFeedback(Base):
    __tablename__ = "message_feedback"
    __table_args__ = (
        CheckConstraint("rating IN ('up','down')", name="rating"),
        UniqueConstraint("message_id", "user_id", name="uq_message_feedback_user"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list[str]] = text_array()
    comment: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = created_at_col()


class RunStep(Base):
    __tablename__ = "run_steps"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('model_call','tool_batch','compaction','delegation',"
            "'approval_wait','memory_recall','finalize')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('running','succeeded','failed','skipped','cancelled')",
            name="status",
        ),
        UniqueConstraint("run_id", "seq", name="uq_run_steps_seq"),
        Index("ix_run_steps_tenant", "tenant_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model_alias: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL")
    )
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, object]] = jsonb_col()
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_tenant", "tenant_id", "run_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
