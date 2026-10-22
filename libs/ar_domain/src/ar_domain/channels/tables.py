"""Channel tables. Spec: docs/04-data/schema.md §14."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk


class ChannelIntegration(Base):
    __tablename__ = "channel_integrations"
    __table_args__ = (
        CheckConstraint("kind IN ('slack','teams','email','widget')", name="kind"),
        CheckConstraint("status IN ('active','disabled','error')", name="status"),
        UniqueConstraint("tenant_id", "kind", "name", name="uq_channel_integrations_kind_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    secret_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret_refs.id", ondelete="RESTRICT")
    )
    default_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL")
    )
    agent_routing: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    status_detail: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ChannelIdentity(Base):
    __tablename__ = "channel_identities"
    __table_args__ = (
        CheckConstraint("match_method IN ('email','scim','manual_link')", name="match_method"),
        UniqueConstraint(
            "integration_id", "external_user_id", name="uq_channel_identities_external"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    match_method: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class ChannelThread(Base):
    __tablename__ = "channel_threads"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_channel_id",
            "external_thread_id",
            name="uq_channel_threads_external",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_channel_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = created_at_col()


class ChannelPost(Base):
    """Durable channel message. OQ-41. The process list is only a flush cache."""

    __tablename__ = "channel_posts"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound','outbound')", name="direction"),
        CheckConstraint("kind IN ('slack','teams','email','widget','webhook')", name="kind"),
        CheckConstraint("status IN ('posted','failed','pending')", name="status"),
        Index("ix_channel_posts_tenant", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_integrations.id", ondelete="CASCADE")
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_threads.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'posted'"))
    detail: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = created_at_col()
