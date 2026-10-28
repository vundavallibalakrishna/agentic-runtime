"""Records tables. Spec: docs/04-data/schema.md §23, §24 and §27."""

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
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, updated_at_col, uuid_pk

_EVIDENCE_STATUS = "'sealed','disposed'"
_METHODS = "'api','tool_call','upload','browser_screenshot','sandbox','run_record'"
_PRINCIPALS = "'user','service_account','system'"
_CLASSES = "'public','internal','confidential','restricted'"
_CUSTODY = "'captured','accessed','exported','verified','hold_applied','hold_released','disposed'"
_HOLD_STATUS = "'active','released'"
_MEMBER_CLASS = (
    "'conversation','run','run_record','evidence_item','document','file',"
    "'memory_fact','signoff','agent_card','audit_archive'"
)
_DISPOSITION = "'delete','archive_then_delete','keep'"
_BINDER = "'draft','pending_review','building','ready','failed'"


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint(f"status IN ({_EVIDENCE_STATUS})", name="status"),
        CheckConstraint("size_bytes >= 0", name="size_bytes"),
        CheckConstraint(f"collection_method IN ({_METHODS})", name="collection_method"),
        CheckConstraint(
            f"collector_principal_type IN ({_PRINCIPALS})", name="collector_principal_type"
        ),
        CheckConstraint(f"classification IN ({_CLASSES})", name="classification"),
        Index("ix_evidence_items_tenant", "tenant_id", text("collected_at DESC")),
        Index("ux_evidence_storage_key", "tenant_id", "storage_key", unique=True),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'sealed'"))
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    worm_locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rfc3161_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signature_key_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_system: Mapped[str] = mapped_column(Text, nullable=False)
    collection_method: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collector_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    collector_tool_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    collector_principal_type: Mapped[str] = mapped_column(Text, nullable=False)
    collector_principal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'internal'")
    )
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    retention_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'evidence_item'")
    )
    created_at: Mapped[datetime] = created_at_col()


class EvidenceCustodyEvent(Base):
    __tablename__ = "evidence_custody_events"
    __table_args__ = (
        CheckConstraint(f"action IN ({_CUSTODY})", name="action"),
        Index("ix_evidence_custody_item", "tenant_id", "evidence_item_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_principal_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_principal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detail: Mapped[dict[str, object]] = jsonb_col()
    audit_event_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = created_at_col()


class LegalHold(Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        CheckConstraint(f"status IN ({_HOLD_STATUS})", name="status"),
        Index("ix_legal_holds_tenant", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    matter: Mapped[str] = mapped_column(Text, nullable=False)
    custodians: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    scope_query: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    approver_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class LegalHoldMember(Base):
    __tablename__ = "legal_hold_members"
    __table_args__ = (
        CheckConstraint(f"record_class IN ({_MEMBER_CLASS})", name="record_class"),
        Index("ix_legal_hold_members_record", "tenant_id", "record_class", "record_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    hold_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_holds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    record_class: Mapped[str] = mapped_column(Text, primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    detail: Mapped[dict[str, object]] = jsonb_col()
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RetentionSchedule(Base):
    __tablename__ = "retention_schedules"
    __table_args__ = (
        CheckConstraint("retention_days >= 1", name="retention_days"),
        CheckConstraint(f"disposition IN ({_DISPOSITION})", name="disposition"),
        UniqueConstraint("tenant_id", "record_class", name="uq_retention_schedules_class"),
        Index("ix_retention_schedules_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    record_class: Mapped[str] = mapped_column(Text, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class DispositionCertificate(Base):
    __tablename__ = "disposition_certificates"
    __table_args__ = (
        Index("ix_disposition_certificates_tenant", "tenant_id", text("disposed_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    record_class: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    disposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    certificate_hash: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class BinderExport(Base):
    __tablename__ = "binder_exports"
    __table_args__ = (
        CheckConstraint(f"status IN ({_BINDER})", name="status"),
        Index("ix_binder_exports_tenant", "tenant_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    selection: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    require_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    review_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_items.id", ondelete="SET NULL")
    )
    manifest_sha256: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
