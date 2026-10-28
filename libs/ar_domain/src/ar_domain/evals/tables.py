"""Evaluation tables. Spec: docs/04-data/schema.md §16."""

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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, text_array, updated_at_col, uuid_pk

_KINDS = "'functional','retrieval','safety','red_team'"
_RUN_STATUS = "'queued','running','completed','failed','cancelled'"
_TRIGGERS = "'manual','publish_gate','schedule','ci'"


class EvalSuite(Base):
    __tablename__ = "eval_suites"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_KINDS})", name="kind"),
        UniqueConstraint("tenant_id", "name", name="uq_eval_suites_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'functional'"))
    gate: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class EvalCase(Base):
    __tablename__ = "eval_cases"
    __table_args__ = (Index("ix_eval_cases_suite", "tenant_id", "suite_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_suites.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    assertions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    tool_mocks: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    tags: Mapped[list[str]] = text_array()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class EvalRunRow(Base):
    """``eval_runs``. The class name avoids the domain service type."""

    __tablename__ = "eval_runs"
    __table_args__ = (
        CheckConstraint(f"status IN ({_RUN_STATUS})", name="status"),
        CheckConstraint(f"trigger IN ({_TRIGGERS})", name="trigger"),
        Index("ix_eval_runs_suite", "tenant_id", "suite_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_suites.id", ondelete="CASCADE"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="SET NULL")
    )
    model_alias_override: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    baseline_eval_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="SET NULL")
    )
    temporal_workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    trigger: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (UniqueConstraint("eval_run_id", "case_id", name="uq_eval_results_case"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_cases.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL")
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    scores: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = created_at_col()


# Alias used by the package export. The table class stays EvalRunRow.
EvalRun = EvalRunRow
