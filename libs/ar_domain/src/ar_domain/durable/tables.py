"""Pack rows shared by the API and the worker."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base


class ExtensionRow(Base):
    """One pack record. The pack id and bucket are columns, not table names."""

    __tablename__ = "extension_rows"
    __table_args__ = (
        Index("ix_extension_rows_tenant_pack", "tenant_id", "pack_id", "bucket"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pack_id: Mapped[str] = mapped_column(Text, nullable=False)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
