"""Run record tables. Spec: docs/04-data/schema.md §22."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import uuid_pk

_REPLAY = "'running','matched','diverged','failed'"


class RunRecord(Base):
    __tablename__ = "run_records"
    __table_args__ = (
        Index("ix_run_records_tenant", "tenant_id", text("sealed_at DESC")),
        Index("ix_run_records_agent", "tenant_id", "agent_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="RESTRICT"), nullable=False
    )
    definition_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_hashes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_revision: Mapped[str | None] = mapped_column(Text)
    weights_digest: Mapped[str | None] = mapped_column(Text)
    sampling_params: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    retrieved: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    output_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signature_key_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_io_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="RESTRICT", name="fk_run_records_evidence"),
    )
    retention_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'run_record'")
    )
    sealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RunRecordReplay(Base):
    __tablename__ = "run_record_replays"
    __table_args__ = (
        CheckConstraint(f"status IN ({_REPLAY})", name="status"),
        Index("ix_run_record_replays_record", "tenant_id", "run_record_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run_records.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    divergence: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
