"""File bytes, workspace files, job progress and A2A push configs."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk


class FileBlobPayload(Base):
    """Bytes copied out of ``file_blobs`` before that table was dropped.

    Hydrate moves each body to the object store. The row is the backfill, not a
    new place to write uploads.
    """

    __tablename__ = "file_blob_payloads"
    __table_args__ = (Index("ix_file_blob_payloads_tenant", "tenant_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class WorkspaceFile(Base):
    """One file under a run workspace. The temp directory can be deleted."""

    __tablename__ = "workspace_files"
    __table_args__ = (
        Index("uq_workspace_files_run_path", "run_id", "path", unique=True),
        Index("ix_workspace_files_run", "tenant_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class JobProgress(Base):
    """Progress for a long OCR, PDF or database job."""

    __tablename__ = "job_progress"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('ocr','pdf','query','workspace')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('running','completed','interrupted','failed')",
            name="status",
        ),
        Index("ix_job_progress_conversation", "tenant_id", "conversation_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'running'"))
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class A2APushConfig(Base):
    """Webhook a client asked us to call when its A2A task changes."""

    __tablename__ = "a2a_push_configs"
    __table_args__ = (
        Index("uq_a2a_push_configs_task_config", "task_id", "config_id", unique=True),
        Index("ix_a2a_push_configs_task", "tenant_id", "task_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("a2a_tasks.id", ondelete="CASCADE"), nullable=False
    )
    key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_api_keys.id", ondelete="CASCADE"), nullable=False
    )
    config_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'default'"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ToolSearchVector(Base):
    """One tool-search embedding, kept per tenant, embedding model and tool text."""

    __tablename__ = "tool_search_vectors"
    __table_args__ = (
        Index(
            "uq_tool_search_vectors_text",
            "tenant_id",
            "model_id",
            "text_hash",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
