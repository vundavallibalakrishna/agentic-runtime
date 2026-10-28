"""Pack registration tables. Spec: docs/04-data/schema.md §28."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, updated_at_col, uuid_pk


class PackRegistration(Base):
    """Platform-or-own. A null tenant id is a built-in registration."""

    __tablename__ = "pack_registrations"
    __table_args__ = (UniqueConstraint("pack_id", "version", name="uq_pack_registrations_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    pack_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class TenantPackFlag(Base):
    __tablename__ = "tenant_pack_flags"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    pack_id: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    settings: Mapped[dict[str, object]] = jsonb_col()
    updated_at: Mapped[datetime] = updated_at_col()
