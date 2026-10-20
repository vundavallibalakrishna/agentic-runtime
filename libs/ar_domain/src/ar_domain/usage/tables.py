"""Usage tables. Spec: docs/04-data/schema.md §15."""

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk

_ZERO = "00000000-0000-0000-0000-000000000000"
_METRICS = (
    "'model_input_tokens','model_output_tokens','model_cached_tokens','embedding_tokens',"
    "'rerank_requests','tool_calls','sandbox_cpu_seconds','sandbox_sessions','storage_bytes','runs'"
)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        CheckConstraint(f"metric IN ({_METRICS})", name="metric"),
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_usage_events_dedupe"),
        Index("ix_usage_events_time", "tenant_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    routine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model_alias: Mapped[str | None] = mapped_column(Text)
    tool_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)


class UsageDaily(Base):
    """Composite primary key matches schema §15."""

    __tablename__ = "usage_daily"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text(f"'{_ZERO}'::uuid"),
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text(f"'{_ZERO}'::uuid"),
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text(f"'{_ZERO}'::uuid"),
    )
    model_alias: Mapped[str] = mapped_column(Text, primary_key=True, server_default=text("''"))
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Quota(Base):
    __tablename__ = "quotas"
    __table_args__ = (
        CheckConstraint("scope_type IN ('tenant','team','user','agent')", name="scope_type"),
        CheckConstraint(
            "metric IN ('cost_micros','model_tokens','runs','sandbox_cpu_seconds','tool_calls')",
            name="metric",
        ),
        CheckConstraint("period IN ('day','month')", name="period"),
        CheckConstraint("limit_value >= 0", name="limit_value"),
        CheckConstraint("action IN ('block','warn')", name="action"),
        CheckConstraint("warn_at_pct BETWEEN 1 AND 100", name="warn_at_pct"),
        UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_id",
            "metric",
            "period",
            name="uq_quotas_scope",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str] = mapped_column(Text, nullable=False)
    limit_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'block'"))
    warn_at_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("80"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
