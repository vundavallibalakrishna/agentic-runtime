"""Sandbox tables. Spec: docs/04-data/schema.md §10."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, text_array, updated_at_col, uuid_pk

_ZERO = "00000000-0000-0000-0000-000000000000"


class SandboxTemplate(Base):
    __tablename__ = "sandbox_templates"
    __table_args__ = (
        CheckConstraint("runtime_class IN ('gvisor','kata','runc_dev')", name="runtime_class"),
        CheckConstraint(
            "max_classification IN ('public','internal','confidential','restricted')",
            name="max_classification",
        ),
        CheckConstraint("status IN ('active','disabled')", name="status"),
        Index(
            "ux_sandbox_templates_slug",
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
    image_ref: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'gvisor'")
    )
    cpu_millis: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("2000"))
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("4096"))
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    allow_browser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    allow_packages: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    egress_allowlist: Mapped[list[str]] = text_array()
    max_classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'confidential'")
    )
    idle_suspend_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("900"))
    max_lifetime_s: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("86400")
    )
    exec_timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("120"))
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("7"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Sandbox(Base):
    __tablename__ = "sandboxes"
    __table_args__ = (
        CheckConstraint("scope IN ('conversation','agent_user','agent')", name="scope"),
        CheckConstraint(
            "status IN ('pending','starting','ready','suspending','suspended','resuming',"
            "'terminating','terminated','failed')",
            name="status",
        ),
        CheckConstraint("driver IN ('docker','kubernetes')", name="driver"),
        Index(
            "ux_sandboxes_live_scope",
            "tenant_id",
            "scope_key",
            unique=True,
            postgresql_where=text("status NOT IN ('terminated','failed')"),
        ),
        Index("ix_sandboxes_idle", "status", "last_active_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sandbox_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    scope_key: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    driver: Mapped[str] = mapped_column(Text, nullable=False)
    driver_ref: Mapped[str | None] = mapped_column(Text)
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    auth_token_hash: Mapped[str | None] = mapped_column(Text)
    workspace_volume: Mapped[str | None] = mapped_column(Text)
    snapshot_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL", name="fk_sandboxes_snapshot"),
    )
    cpu_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
