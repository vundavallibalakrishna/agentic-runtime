"""Saved table queries. Spec: docs/04-data/schema.md §32."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, uuid_pk


class SavedQuery(Base):
    """One version of a named query. A version is written once and never changed."""

    __tablename__ = "saved_queries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_saved_queries_version"),
        Index("ix_saved_queries_tenant", "tenant_id", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
