"""Tool tables. Spec: docs/04-data/schema.md §6."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, text_array, updated_at_col, uuid_pk

_ZERO = "00000000-0000-0000-0000-000000000000"
_CLASS = "('public','internal','confidential','restricted')"


class DataConnection(Base):
    __tablename__ = "data_connections"
    __table_args__ = (
        CheckConstraint(
            "engine IN ('postgres','mysql','mssql','oracle','snowflake','trino','clickhouse')",
            name="engine",
        ),
        CheckConstraint(
            "identity_mode IN ('service','per_user_mapped','passthrough')",
            name="identity_mode",
        ),
        CheckConstraint("row_limit BETWEEN 1 AND 100000", name="row_limit"),
        CheckConstraint("statement_timeout_s BETWEEN 1 AND 600", name="statement_timeout_s"),
        CheckConstraint(f"classification IN {_CLASS}", name="classification"),
        CheckConstraint("status IN ('active','disabled')", name="status"),
        UniqueConstraint("tenant_id", "name", name="uq_data_connections_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str] = mapped_column(Text, nullable=False)
    dsn_secret_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret_refs.id", ondelete="RESTRICT"), nullable=False
    )
    identity_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'service'")
    )
    allowlist: Mapped[dict[str, object]] = jsonb_col()
    row_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1000"))
    statement_timeout_s: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'internal'")
    )
    schema_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ToolServer(Base):
    __tablename__ = "tool_servers"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z][a-z0-9_]{1,30}$'", name="slug"),
        CheckConstraint(
            "kind IN ('remote_mcp','openapi','sql','builtin','sandbox')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('draft','pending_review','approved','deprecated','rejected')",
            name="status",
        ),
        Index(
            "ux_tool_servers_slug",
            text(f"coalesce(tenant_id, '{_ZERO}'::uuid)"),
            "slug",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    owner_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL")
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tool_server_versions.id",
            name="fk_ts_current",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ToolServerVersion(Base):
    __tablename__ = "tool_server_versions"
    __table_args__ = (
        CheckConstraint("version ~ '^\\d+\\.\\d+\\.\\d+$'", name="version"),
        CheckConstraint(
            "auth_mode IN ('none','static_secret','user_oauth','token_exchange','internal_jwt')",
            name="auth_mode",
        ),
        CheckConstraint(
            "review_status IN ('pending','approved','rejected')",
            name="review_status",
        ),
        UniqueConstraint("tool_server_id", "version", name="uq_tool_server_versions"),
        Index("ix_tsv_tenant", "tenant_id", "tool_server_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    tool_server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_servers.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, object]] = jsonb_col()
    auth_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'none'"))
    secret_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret_refs.id", ondelete="RESTRICT")
    )
    credential_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credential_providers.id", ondelete="RESTRICT")
    )
    manifest: Mapped[dict[str, object]] = jsonb_col()
    manifest_hash: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    review_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    review_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class Tool(Base):
    __tablename__ = "tools"
    __table_args__ = (
        CheckConstraint("name ~ '^[a-z][a-z0-9_]{0,47}$'", name="name"),
        UniqueConstraint("tool_server_id", "name", name="uq_tools_name"),
        Index("ix_tools_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    tool_server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_servers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ToolVersion(Base):
    __tablename__ = "tool_versions"
    __table_args__ = (
        CheckConstraint("risk_class IN ('R0','R1','W1','W2','W3')", name="risk_class"),
        CheckConstraint(f"data_classification IN {_CLASS}", name="data_classification"),
        CheckConstraint("timeout_s BETWEEN 1 AND 900", name="timeout_s"),
        UniqueConstraint("tool_id", "tool_server_version_id", name="uq_tool_versions"),
        Index("ix_tool_versions_tenant", "tenant_id", "tool_id"),
        Index(
            "ix_tool_versions_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
    tool_server_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tool_server_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_hash: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    annotations: Mapped[dict[str, object]] = jsonb_col()
    risk_class: Mapped[str] = mapped_column(Text, nullable=False)
    data_classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'internal'")
    )
    required_scopes: Mapped[list[str]] = text_array()
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("60"))
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    max_result_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("65536")
    )
    idempotent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approval_preview: Mapped[dict[str, object]] = jsonb_col()
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = created_at_col()


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        CheckConstraint(
            "policy_decision IN ('allow','deny','require_approval')",
            name="policy_decision",
        ),
        CheckConstraint(
            "status IN ('pending','awaiting_approval','running','succeeded','failed',"
            "'denied','rejected','expired','cancelled')",
            name="status",
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_tool_calls_idempotency"),
        Index("ix_tool_calls_run", "tenant_id", "run_id"),
        Index("ix_tool_calls_tool", "tenant_id", "tool_id", "created_at"),
        ForeignKeyConstraint(
            ["approval_id"],
            ["approvals.id"],
            name="fk_tool_calls_approval",
            ondelete="SET NULL",
            use_alter=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    run_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run_steps.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="SET NULL")
    )
    tool_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_versions.id", ondelete="SET NULL")
    )
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_call_id: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_redacted: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    args_hash: Mapped[str] = mapped_column(Text, nullable=False)
    risk_class: Mapped[str] = mapped_column(Text, nullable=False)
    policy_decision: Mapped[str | None] = mapped_column(Text)
    policy_reasons: Mapped[list[str]] = text_array()
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    result_preview: Mapped[str | None] = mapped_column(Text)
    result_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", name="fk_tool_calls_result", ondelete="SET NULL", use_alter=True),
    )
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    error: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
