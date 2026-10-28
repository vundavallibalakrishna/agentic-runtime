"""Schema `grc`. These models are not on the core metadata."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any  # noqa: TC003 - SQLAlchemy resolves Mapped annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class PackBase(DeclarativeBase):
    """Pack metadata only. Core Alembic does not see these tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _tenant() -> Mapped[uuid.UUID]:
    """Tenant key. ``link_to_name`` keeps core tables out of this metadata."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE", link_to_name=True),
        nullable=False,
    )


def _schema(*items: object) -> tuple[object, ...]:
    return (*items, {"schema": "grc"})


def _json(default: str = "'{}'::jsonb") -> Mapped[dict[str, Any]]:
    return mapped_column(JSONB, nullable=False, server_default=text(default))


def _text(default: str | None = None) -> Mapped[str]:
    if default is None:
        return mapped_column(Text, nullable=False)
    return mapped_column(Text, nullable=False, server_default=text(default))


class Framework(PackBase):
    __tablename__ = "frameworks"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "key", "version", name="uq_frameworks_tenant_key_version"),
        CheckConstraint("licence IN ('free', 'skeleton')", name="ck_frameworks_licence"),
        Index("ix_grc_frameworks_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    licence: Mapped[str] = mapped_column(Text, nullable=False)
    pack_owned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Requirement(PackBase):
    __tablename__ = "requirements"
    __table_args__ = _schema(
        UniqueConstraint("framework_id", "key", name="uq_requirements_framework_key"),
        Index("ix_grc_requirements_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.frameworks.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = _text("''")


class Entity(PackBase):
    __tablename__ = "entities"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "name", name="uq_entities_tenant_name"),
        CheckConstraint("kind IN ('legal_entity', 'division', 'region')", name="ck_entities_kind"),
        Index("ix_grc_entities_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.entities.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)


class Control(PackBase):
    __tablename__ = "controls"
    __table_args__ = _schema(
        UniqueConstraint(
            "tenant_id", "framework_id", "key", name="uq_controls_tenant_framework_key"
        ),
        Index(
            "uq_grc_controls_common_key",
            "tenant_id",
            "key",
            unique=True,
            postgresql_where=text("framework_id IS NULL"),
        ),
        Index("ix_grc_controls_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    framework_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.frameworks.id", ondelete="CASCADE")
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.entities.id", ondelete="SET NULL")
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = _text("''")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ControlMapping(PackBase):
    __tablename__ = "control_mappings"
    __table_args__ = _schema(
        UniqueConstraint(
            "tenant_id",
            "from_control_id",
            "to_control_id",
            name="uq_control_mappings_pair",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_control_mappings_confidence"
        ),
        CheckConstraint(
            "status IN ('suggested', 'confirmed', 'rejected')", name="ck_control_mappings_status"
        ),
        CheckConstraint("from_control_id <> to_control_id", name="ck_control_mappings_distinct"),
        Index("ix_grc_control_mappings_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    from_control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.controls.id", ondelete="CASCADE"), nullable=False
    )
    to_control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.controls.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    rationale: Mapped[str] = _text("''")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    confirmed_at: Mapped[datetime | None] = mapped_column()


class ControlTest(PackBase):
    __tablename__ = "control_tests"
    __table_args__ = _schema(
        UniqueConstraint("control_id", "key", name="uq_control_tests_key"),
        CheckConstraint("freshness_days >= 1", name="ck_control_tests_freshness"),
        Index("ix_grc_control_tests_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.controls.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    procedure: Mapped[str] = mapped_column(Text, nullable=False)
    schedule: Mapped[str] = mapped_column(Text, nullable=False)
    freshness_days: Mapped[int] = mapped_column(Integer, nullable=False)


class TestResult(PackBase):
    __tablename__ = "test_results"
    __table_args__ = _schema(
        CheckConstraint("outcome IN ('pass', 'fail', 'error')", name="ck_test_results_outcome"),
        Index("ix_grc_test_results_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.control_tests.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    run_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detail: Mapped[dict[str, Any]] = _json()
    created_at: Mapped[datetime] = created_at_col()


class EvidenceLink(PackBase):
    __tablename__ = "evidence_links"
    __table_args__ = _schema(
        UniqueConstraint("control_id", "evidence_item_id", name="uq_evidence_links_pair"),
        CheckConstraint("freshness_days >= 1", name="ck_evidence_links_freshness"),
        Index("ix_grc_evidence_links_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.controls.id", ondelete="CASCADE"), nullable=False
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="RESTRICT", link_to_name=True),
        nullable=False,
    )
    freshness_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class Asset(PackBase):
    __tablename__ = "assets"
    __table_args__ = _schema(Index("ix_grc_assets_tenant_id", "tenant_id"))

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    agent_card_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tier: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class Risk(PackBase):
    __tablename__ = "risks"
    __table_args__ = _schema(
        CheckConstraint(
            "status IN ('open', 'treating', 'accepted', 'closed')", name="ck_risks_status"
        ),
        CheckConstraint("source IN ('human', 'agent')", name="ck_risks_source"),
        Index("ix_grc_risks_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.assets.id", ondelete="SET NULL")
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.entities.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'human'"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class RiskAssessment(PackBase):
    __tablename__ = "risk_assessments"
    __table_args__ = _schema(
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_risk_assessments_likelihood"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_risk_assessments_impact"),
        CheckConstraint("score = likelihood * impact", name="ck_risk_assessments_score"),
        Index("ix_grc_risk_assessments_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.risks.id", ondelete="CASCADE"), nullable=False
    )
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = created_at_col()


class Treatment(PackBase):
    __tablename__ = "treatments"
    __table_args__ = _schema(
        CheckConstraint("kind IN ('mitigate', 'transfer', 'avoid')", name="ck_treatments_kind"),
        CheckConstraint("status IN ('open', 'done')", name="ck_treatments_status"),
        Index("ix_grc_treatments_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.risks.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    due_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))


class Vendor(PackBase):
    __tablename__ = "vendors"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "name", name="uq_vendors_tenant_name"),
        CheckConstraint("tier IN ('critical', 'high', 'medium', 'low')", name="ck_vendors_tier"),
        Index("ix_grc_vendors_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.entities.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class VendorAssessment(PackBase):
    __tablename__ = "vendor_assessments"
    __table_args__ = _schema(
        CheckConstraint(
            "kind IN ('intake', 'questionnaire', 'document_review')",
            name="ck_vendor_assessments_kind",
        ),
        CheckConstraint("status IN ('open', 'scored')", name="ck_vendor_assessments_status"),
        Index("ix_grc_vendor_assessments_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.vendors.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    tier: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str] = _text("''")
    due_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()


class Finding(PackBase):
    __tablename__ = "findings"
    __table_args__ = _schema(
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')", name="ck_findings_severity"
        ),
        CheckConstraint("status IN ('open', 'closed')", name="ck_findings_status"),
        Index("ix_grc_findings_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    control_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.controls.id", ondelete="SET NULL")
    )
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    due_at: Mapped[datetime | None] = mapped_column()
    closure_evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Issue(PackBase):
    __tablename__ = "issues"
    __table_args__ = _schema(
        CheckConstraint("status IN ('open', 'done')", name="ck_issues_status"),
        Index("ix_grc_issues_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.findings.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    due_at: Mapped[datetime | None] = mapped_column()
    external_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Policy(PackBase):
    __tablename__ = "policies"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "key", name="uq_policies_tenant_key"),
        Index("ix_grc_policies_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.entities.id", ondelete="SET NULL")
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    created_at: Mapped[datetime] = created_at_col()


class PolicyVersion(PackBase):
    __tablename__ = "policy_versions"
    __table_args__ = _schema(
        UniqueConstraint("policy_id", "version", name="uq_policy_versions_number"),
        CheckConstraint("state IN ('draft', 'published')", name="ck_policy_versions_state"),
        Index("ix_grc_policy_versions_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.policies.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    review_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Obligation(PackBase):
    __tablename__ = "obligations"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "regulator", "citation", name="uq_obligations_citation"),
        CheckConstraint("status IN ('active', 'retired')", name="ck_obligations_status"),
        Index("ix_grc_obligations_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    regulator: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )


class RegulatoryChange(PackBase):
    __tablename__ = "regulatory_changes"
    __table_args__ = _schema(
        CheckConstraint(
            "status IN ('new', 'triaged', 'dismissed')", name="ck_regulatory_changes_status"
        ),
        Index("ix_grc_regulatory_changes_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    feed_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    note: Mapped[str] = _text("''")
    created_at: Mapped[datetime] = created_at_col()


class Incident(PackBase):
    __tablename__ = "incidents"
    __table_args__ = _schema(
        CheckConstraint("status IN ('open', 'notified', 'closed')", name="ck_incidents_status"),
        Index("ix_grc_incidents_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = _text("''")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    detected_at: Mapped[datetime] = mapped_column(nullable=False)
    clocks: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Campaign(PackBase):
    __tablename__ = "campaigns"
    __table_args__ = _schema(
        CheckConstraint(
            "kind IN ('questionnaire', 'vendor', 'acknowledgement', 'attestation',"
            " 'access_review')",
            name="ck_campaigns_kind",
        ),
        CheckConstraint("status IN ('draft', 'running', 'closed')", name="ck_campaigns_status"),
        Index("ix_grc_campaigns_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    due_at: Mapped[datetime | None] = mapped_column()
    audience: Mapped[dict[str, Any]] = _json()
    created_at: Mapped[datetime] = created_at_col()


class CampaignItem(PackBase):
    __tablename__ = "campaign_items"
    __table_args__ = _schema(
        UniqueConstraint(
            "campaign_id",
            "assignee_user_id",
            "assignee_guest_id",
            name="uq_campaign_items_assignee",
        ),
        CheckConstraint("status IN ('open', 'decided')", name="ck_campaign_items_status"),
        Index("ix_grc_campaign_items_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.campaigns.id", ondelete="CASCADE"), nullable=False
    )
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    assignee_guest_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    decision: Mapped[str | None] = mapped_column(Text)
    statement_text: Mapped[str] = _text("''")
    statement_hash: Mapped[str | None] = mapped_column(Text)
    review_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Answer(PackBase):
    __tablename__ = "answer_library"
    __table_args__ = _schema(
        CheckConstraint(
            "status IN ('draft', 'approved', 'expired')", name="ck_answer_library_status"
        ),
        Index("ix_grc_answer_library_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_md: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    expires_at: Mapped[datetime | None] = mapped_column()
    citations: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class PbcRequest(PackBase):
    __tablename__ = "pbc_requests"
    __table_args__ = _schema(
        CheckConstraint(
            "status IN ('open', 'responded', 'provided', 'accepted')",
            name="ck_pbc_requests_status",
        ),
        Index("ix_grc_pbc_requests_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    control_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc.controls.id", ondelete="SET NULL")
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", link_to_name=True)
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    response_md: Mapped[str] = _text("''")
    due_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Entitlement(PackBase):
    __tablename__ = "entitlements"
    __table_args__ = _schema(
        UniqueConstraint(
            "tenant_id", "source", "subject", "entitlement", name="uq_entitlements_subject"
        ),
        CheckConstraint("source IN ('okta', 'entra', 'google')", name="ck_entitlements_source"),
        Index("ix_grc_entitlements_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    source: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    entitlement: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(nullable=False)
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SodRule(PackBase):
    __tablename__ = "sod_rules"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "entitlement_a", "entitlement_b", name="uq_sod_rules_pair"),
        CheckConstraint("entitlement_a <> entitlement_b", name="ck_sod_rules_distinct"),
        Index("ix_grc_sod_rules_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entitlement_a: Mapped[str] = mapped_column(Text, nullable=False)
    entitlement_b: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class Inspection(PackBase):
    __tablename__ = "inspections"
    __table_args__ = _schema(
        CheckConstraint(
            "status IN ('announced', 'in_progress', 'closed')",
            name="ck_inspections_status",
        ),
        Index("ix_grc_inspections_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    regulator: Mapped[str] = mapped_column(Text, nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'announced'"))
    binder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class DsarRequest(PackBase):
    __tablename__ = "dsar_requests"
    __table_args__ = _schema(
        CheckConstraint(
            "request_type IN ('access', 'correction', 'erasure', 'portability')",
            name="ck_dsar_requests_request_type",
        ),
        CheckConstraint(
            "status IN ('open', 'fulfilled', 'refused')",
            name="ck_dsar_requests_status",
        ),
        Index("ix_grc_dsar_requests_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    request_type: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ConsentRecord(PackBase):
    __tablename__ = "consent_records"
    __table_args__ = _schema(
        CheckConstraint("state IN ('granted', 'withdrawn')", name="ck_consent_records_state"),
        Index("ix_grc_consent_records_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    subject_ref: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_at: Mapped[datetime] = created_at_col()


class ResilienceTest(PackBase):
    __tablename__ = "resilience_tests"
    __table_args__ = _schema(
        CheckConstraint("kind IN ('bcp', 'dr')", name="ck_resilience_tests_kind"),
        CheckConstraint(
            "outcome IN ('pass', 'fail', 'partial')",
            name="ck_resilience_tests_outcome",
        ),
        Index("ix_grc_resilience_tests_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    tested_on: Mapped[date] = mapped_column(Date, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class RegulatorFeed(PackBase):
    __tablename__ = "regulator_feeds"
    __table_args__ = _schema(
        UniqueConstraint("tenant_id", "regulator", name="uq_regulator_feeds_regulator"),
        Index("ix_grc_regulator_feeds_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    regulator: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


def _external_stub(name: str) -> None:
    """Let foreign keys resolve without putting core tables on the pack head."""
    if name in PackBase.metadata.tables:
        return
    Table(name, PackBase.metadata, Column("id", UUID(as_uuid=True), primary_key=True))


for _external_name in ("tenants", "users", "evidence_items"):
    _external_stub(_external_name)


TABLES_WITH_UPDATED_AT = (
    "frameworks",
    "controls",
    "risks",
    "vendors",
    "findings",
    "issues",
    "answer_library",
    "pbc_requests",
    "incidents",
)
