"""Rule sets and judgements. The document they cite is ``documents``. Schema section 31."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk


class DocumentCheck(Base):
    __tablename__ = "document_checks"
    __table_args__ = (Index("ix_document_checks_document", "tenant_id", "document_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    standard_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    rows: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class DocumentComparison(Base):
    __tablename__ = "document_comparisons"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    left_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    right_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    changes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class DocumentRewrite(Base):
    __tablename__ = "document_rewrites"
    __table_args__ = (
        CheckConstraint("status IN ('proposed','accepted','rejected')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    anchor: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    passage_anchors: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    instruction: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    original: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    proposed: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    hunks: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'proposed'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class RuleSet(Base):
    """One immutable version of a tenant rule set."""

    __tablename__ = "rule_sets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "set_id", "version", name="uq_rule_sets_version"),
        Index("ix_rule_sets_tenant", "tenant_id", "set_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    set_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    items: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    sha256: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class Judgement(Base):
    """One quote check. Append-only."""

    __tablename__ = "judgements"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('supported','not_supported','not_judged','failed')",
            name="verdict",
        ),
        Index("ix_judgements_document", "tenant_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    rule_set_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    rule_set_version: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    item_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    passage_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    quote: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    model_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
