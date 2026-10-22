"""Approval, review and segregation tables. Spec: docs/04-data/schema.md §7 and §21."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, text_array, updated_at_col, uuid_pk

_SUBJECTS = (
    "('artifact','file','message','evidence_item','run_record','agent_card','binder','pack_record')"
)


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','expired','cancelled')",
            name="status",
        ),
        CheckConstraint("required_approvals BETWEEN 1 AND 5", name="required_approvals"),
        UniqueConstraint("tool_call_id", name="uq_approvals_tool_call_id"),
        Index(
            "ix_approvals_pending",
            "tenant_id",
            "status",
            "expires_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_approvals_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    tool_call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    requested_for_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    risk_class: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    args_hash: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict[str, object]] = jsonb_col()
    preview: Mapped[dict[str, object]] = jsonb_col()
    justification: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    approver_rule: Mapped[dict[str, object]] = jsonb_col()
    required_approvals: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    step_up_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    policy_reasons: Mapped[list[str]] = text_array()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('approve','reject')", name="decision"),
        CheckConstraint(
            "channel IN ('web','slack','teams','email','api')",
            name="channel",
        ),
        UniqueConstraint("approval_id", "approver_user_id", name="uq_approval_decisions_approver"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approvals.id", ondelete="CASCADE"), nullable=False
    )
    approver_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    args_hash: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    step_up_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class StandingApproval(Base):
    __tablename__ = "standing_approvals"
    __table_args__ = (
        CheckConstraint("agent_id IS NOT NULL OR routine_id IS NOT NULL", name="target"),
        Index(
            "ix_standing_approvals_lookup",
            "tenant_id",
            "tool_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    routine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
    argument_constraints: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    max_uses: Mapped[int | None] = mapped_column(Integer)
    uses: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class ReviewQueue(Base):
    __tablename__ = "review_queues"
    __table_args__ = (
        CheckConstraint(f"subject_type IN {_SUBJECTS}", name="subject_type"),
        UniqueConstraint("tenant_id", "slug", name="uq_review_queues_slug"),
        Index("ix_review_queues_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    levels: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    statement_template: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ReviewItem(Base):
    __tablename__ = "review_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','in_review','signed','rejected','expired','superseded')",
            name="status",
        ),
        CheckConstraint(
            "preparer_principal_type IN ('user','service_account','guest')",
            name="preparer_principal_type",
        ),
        Index("ix_review_items_queue", "tenant_id", "queue_id", "status"),
        Index("ix_review_items_subject", "tenant_id", "subject_type", "subject_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_queues.id", ondelete="RESTRICT"), nullable=False
    )
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_ref: Mapped[dict[str, object]] = jsonb_col()
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    statement_text: Mapped[str] = mapped_column(Text, nullable=False)
    statement_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    preparer_principal_type: Mapped[str] = mapped_column(Text, nullable=False)
    preparer_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Signoff(Base):
    __tablename__ = "signoffs"
    __table_args__ = (
        CheckConstraint("decision IN ('approve','reject','delegate')", name="decision"),
        CheckConstraint("signer_principal_type IN ('user','guest')", name="signer_principal_type"),
        Index("ix_signoffs_item", "tenant_id", "review_item_id", "level"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    review_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_items.id", ondelete="RESTRICT"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    signer_principal_type: Mapped[str] = mapped_column(Text, nullable=False)
    signer_principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    signer_role_key: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    statement_hash: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    step_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delegated_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class SodConstraint(Base):
    __tablename__ = "sod_constraints"
    __table_args__ = (
        CheckConstraint("kind IN ('conflicting_roles')", name="kind"),
        CheckConstraint("applies_to IN ('approval','signoff','both')", name="applies_to"),
        CheckConstraint("role_a <> role_b", name="roles_differ"),
        UniqueConstraint(
            "tenant_id", "role_a", "role_b", "applies_to", name="uq_sod_constraints_roles"
        ),
        Index("ix_sod_constraints_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'conflicting_roles'")
    )
    role_a: Mapped[str] = mapped_column(Text, nullable=False)
    role_b: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
