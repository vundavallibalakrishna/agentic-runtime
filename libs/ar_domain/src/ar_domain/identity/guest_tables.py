"""Guest principal tables. Spec: docs/04-data/schema.md §26."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk

_KIND = "'external','partner','other'"
_STATUS = "'invited','active','expired','revoked'"
_AUTH = "'magic_link_totp','federated'"


class GuestPrincipal(Base):
    __tablename__ = "guest_principals"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_KIND})", name="kind"),
        CheckConstraint(f"status IN ({_STATUS})", name="status"),
        CheckConstraint(f"auth_method IN ({_AUTH})", name="auth_method"),
        UniqueConstraint("tenant_id", "email", name="uq_guest_principals_email"),
        Index("ix_guest_principals_tenant", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'invited'"))
    auth_method: Mapped[str] = mapped_column(Text, nullable=False)
    totp_secret_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("secret_refs.id", ondelete="SET NULL", name="fk_guest_totp_secret"),
    )
    federated_subject: Mapped[str | None] = mapped_column(Text)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class GuestGrant(Base):
    __tablename__ = "guest_grants"
    __table_args__ = (
        CheckConstraint("portal ~ '^[a-z][a-z0-9_]{0,40}$'", name="portal"),
        Index("ix_guest_grants_guest", "tenant_id", "guest_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_principals.id", ondelete="CASCADE"), nullable=False
    )
    portal: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    watermark: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_at_col()


class GuestLoginChallenge(Base):
    __tablename__ = "guest_login_challenges"
    __table_args__ = (Index("ix_guest_login_challenges_guest", "tenant_id", "guest_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_principals.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
