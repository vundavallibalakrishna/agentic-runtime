"""AI governance tables. Spec: docs/04-data/schema.md §25."""

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, text_array, updated_at_col, uuid_pk

_OVERSIGHT = "'autonomous_r0','approval','human_in_loop'"
_SEVERITY = "'low','medium','high'"
_INCIDENT = "'open','mitigated','closed'"


class AgentCard(Base):
    __tablename__ = "agent_cards"
    __table_args__ = (
        CheckConstraint(f"oversight_mode IN ({_OVERSIGHT})", name="oversight_mode"),
        Index("ix_agent_cards_agent", "tenant_id", "agent_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    risk_tier: Mapped[str] = mapped_column(Text, nullable=False)
    data_categories: Mapped[list[str]] = text_array()
    oversight_mode: Mapped[str] = mapped_column(Text, nullable=False)
    eval_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    known_limitations: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    review_due_at: Mapped[date | None] = mapped_column(Date)
    card_hash: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = created_at_col()


class AiIncident(Base):
    __tablename__ = "ai_incidents"
    __table_args__ = (
        CheckConstraint(f"severity IN ({_SEVERITY})", name="severity"),
        CheckConstraint(f"status IN ({_INCIDENT})", name="status"),
        Index("ix_ai_incidents_tenant", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL")
    )
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="SET NULL")
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL")
    )
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class AiOversightDaily(Base):
    __tablename__ = "ai_oversight_daily"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    approvals_requested: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    approvals_approved: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    approvals_rejected: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    signoffs_approved: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    signoffs_rejected: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    overrides: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
