"""Connector installs and the rows that must survive a restart. Revision 0028."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk

_EMPTY = r"'\x'::bytea"


class ConnectorInstall(Base):
    """A catalogue connector turned on for one person. The secret stays on the connection."""

    __tablename__ = "connector_installs"
    __table_args__ = (
        CheckConstraint("status IN ('installed','disabled')", name="status"),
        Index(
            "ux_connector_installs_owner_slug",
            "tenant_id",
            "owner_user_id",
            "slug",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    connection_name: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_connections.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'installed'"))
    disabled_tools: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    config: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class OauthState(Base):
    """One in-flight OAuth state. The verifier is ciphertext."""

    __tablename__ = "oauth_states"
    __table_args__ = (Index("ix_oauth_states_tenant", "tenant_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credential_providers.id", ondelete="CASCADE")
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_connections.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    verifier: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, server_default=text(_EMPTY)
    )
    created_at: Mapped[datetime] = created_at_col()


class NamedSecret(Base):
    """A secret addressed by name. The API never returns the ciphertext."""

    __tablename__ = "named_secrets"
    __table_args__ = (
        Index("ux_named_secrets_name", "tenant_id", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, server_default=text(_EMPTY)
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
