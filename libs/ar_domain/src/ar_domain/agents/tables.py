"""Agent tables. Spec: docs/04-data/schema.md §4."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk

_ZERO = "00000000-0000-0000-0000-000000000000"


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="slug"),
        CheckConstraint("visibility IN ('private','team','tenant')", name="visibility"),
        CheckConstraint("status IN ('draft','published','archived')", name="status"),
        CheckConstraint("risk_tier IN ('low','medium','high')", name="risk_tier"),
        UniqueConstraint("tenant_id", "slug", name="uq_agents_slug"),
        Index("ix_agents_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", name="fk_agents_avatar", ondelete="SET NULL", use_alter=True),
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    owner_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL")
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'private'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    risk_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'low'"))
    draft_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "agent_versions.id",
            name="fk_agents_draft",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "agent_versions.id",
            name="fk_agents_published",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        CheckConstraint("state IN ('draft','published','superseded')", name="state"),
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_version"),
        Index("ix_agent_versions_tenant", "tenant_id", "agent_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    definition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    definition_hash: Mapped[str] = mapped_column(Text, nullable=False)
    change_note: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class AgentVersionBinding(Base):
    __tablename__ = "agent_version_bindings"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('tool','tool_server','knowledge_collection','skill','subagent',"
            "'sandbox_template','model_alias')",
            name="kind",
        ),
        Index("ix_avb_target", "tenant_id", "kind", "target_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text(f"'{_ZERO}'::uuid"),
    )
    target_key: Mapped[str] = mapped_column(Text, primary_key=True, server_default=text("''"))
