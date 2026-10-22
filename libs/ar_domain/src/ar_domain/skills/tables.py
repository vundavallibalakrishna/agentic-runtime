"""Skill tables. Spec: docs/04-data/schema.md §12."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, text_array, updated_at_col, uuid_pk


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="slug"),
        CheckConstraint("length(description) <= 500", name="description_len"),
        CheckConstraint("visibility IN ('private','team','tenant')", name="visibility"),
        CheckConstraint("status IN ('draft','published','archived')", name="status"),
        UniqueConstraint("tenant_id", "slug", name="uq_skills_slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    owner_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL")
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="tenant")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        CheckConstraint("version >= 0", name="version_non_negative"),
        CheckConstraint("length(instructions_md) <= 50000", name="instructions_len"),
        UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions_md: Mapped[str] = mapped_column(Text, nullable=False)
    assets: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    required_tools: Mapped[list[str]] = text_array()
    hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
