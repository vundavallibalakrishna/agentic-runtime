"""Routine tables. Spec: docs/04-data/schema.md §13."""

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk


class Routine(Base):
    __tablename__ = "routines"
    __table_args__ = (
        CheckConstraint("run_as IN ('owner','service_account')", name="run_as"),
        CheckConstraint(
            "run_as = 'owner' OR service_account_id IS NOT NULL",
            name="service_account",
        ),
        CheckConstraint("length(instructions) <= 20000", name="instructions_len"),
        CheckConstraint(
            "trigger_type IN ('schedule','webhook','channel_event','email',"
            "'file_arrival','db_change','manual')",
            name="trigger_type",
        ),
        CheckConstraint("max_runs_per_day BETWEEN 1 AND 10000", name="max_runs"),
        CheckConstraint(
            "concurrency_policy IN ('skip','buffer_one','allow')",
            name="concurrency",
        ),
        CheckConstraint(
            "status IN ('active','paused','needs_review','disabled')",
            name="status",
        ),
        UniqueConstraint("webhook_path_token", name="uq_routines_webhook_token"),
        Index("ix_routines_tenant", "tenant_id", "status"),
        Index("ix_routines_owner", "tenant_id", "owner_user_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    run_as: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'owner'"))
    service_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_accounts.id", ondelete="RESTRICT")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="SET NULL")
    )
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    event_filter: Mapped[str | None] = mapped_column(Text)
    delivery: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    budget: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    max_runs_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("48")
    )
    concurrency_policy: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'skip'")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    paused_reason: Mapped[str | None] = mapped_column(Text)
    temporal_schedule_id: Mapped[str | None] = mapped_column(Text)
    webhook_path_token: Mapped[str | None] = mapped_column(Text)
    webhook_secret_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret_refs.id", ondelete="SET NULL")
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class RoutineEvent(Base):
    __tablename__ = "routine_events"
    __table_args__ = (
        CheckConstraint(
            "source IN ('schedule','webhook','slack','teams','email','s3','db','manual')",
            name="source",
        ),
        CheckConstraint(
            "status IN ('accepted','duplicate','filtered','rate_limited',"
            "'skipped_concurrency','started','failed')",
            name="status",
        ),
        UniqueConstraint("routine_id", "idempotency_key", name="uq_routine_events_idempotency"),
        Index(
            "ix_routine_events_routine",
            "tenant_id",
            "routine_id",
            text("received_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    envelope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    payload_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL")
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
