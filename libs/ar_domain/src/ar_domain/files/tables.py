"""File table. Spec: docs/04-data/schema.md §11. Later FKs wait for their tables."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, updated_at_col, uuid_pk


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('upload','artifact','tool_result','sandbox_snapshot','knowledge_raw',"
            "'knowledge_parsed','skill_asset','avatar','export','openapi_spec','eval_dataset',"
            "'event_payload')",
            name="kind",
        ),
        CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name="classification",
        ),
        CheckConstraint(
            "status IN ('pending_upload','ready','quarantined','deleted')",
            name="status",
        ),
        CheckConstraint(
            "scan_status IN ('pending','clean','infected','skipped','error')",
            name="scan_status",
        ),
        Index(
            "ix_files_owner",
            "tenant_id",
            "owner_user_id",
            text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_files_conversation", "tenant_id", "conversation_id"),
        Index(
            "ix_files_retention",
            "retention_until",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    sha256: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'internal'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending_upload'")
    )
    scan_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    preview: Mapped[dict[str, object]] = jsonb_col()
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
