"""Model registry tables. Spec: docs/04-data/schema.md §3."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, text_array, updated_at_col, uuid_pk

_ZERO = "00000000-0000-0000-0000-000000000000"


class ModelProvider(Base):
    __tablename__ = "model_providers"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('openai_compatible','vllm','tei','fake')",
            name="kind",
        ),
        CheckConstraint("timeout_s BETWEEN 1 AND 900", name="timeout_s"),
        CheckConstraint("status IN ('active','disabled')", name="status"),
        Index("ix_model_providers_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret_refs.id", ondelete="SET NULL")
    )
    headers: Mapped[dict[str, object]] = jsonb_col()
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("120"))
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("64"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    health: Mapped[dict[str, object]] = jsonb_col()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Model(Base):
    __tablename__ = "models"
    __table_args__ = (
        CheckConstraint("kind IN ('chat','embedding','rerank')", name="kind"),
        CheckConstraint("status IN ('active','disabled','deprecated')", name="status"),
        Index("ix_models_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_providers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_model: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[list[str]] = text_array()
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    price_input_micros_per_mtok: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    price_output_micros_per_mtok: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    licence: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class ModelAlias(Base):
    __tablename__ = "model_aliases"
    __table_args__ = (
        CheckConstraint("alias ~ '^[a-z][a-z0-9_-]{1,40}$'", name="alias"),
        CheckConstraint("kind IN ('chat','embedding','rerank')", name="kind"),
        CheckConstraint("status IN ('active','disabled')", name="status"),
        Index(
            "ux_model_aliases",
            text(f"coalesce(tenant_id, '{_ZERO}'::uuid)"),
            "alias",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    primary_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="RESTRICT"), nullable=False
    )
    fallback_model_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
    )
    traffic_split: Mapped[dict[str, object]] = jsonb_col()
    default_params: Mapped[dict[str, object]] = jsonb_col()
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
