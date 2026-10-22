"""Memory facts. Spec: docs/04-data/schema.md §9."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from pgvector.sqlalchemy import Vector
from sqlalchemy import REAL, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, updated_at_col, uuid_pk

_SCOPES = "('user','agent','team','agent_user')"
_CATEGORIES = "('preference','fact','instruction','lesson','contact','glossary')"
_SOURCES = "('explicit','extracted','tool_output','admin','import')"
_TRUST = "('high','low')"
_STATUS = "('active','pending_review','superseded','deleted')"


class MemoryFact(Base):
    """One long-term fact. Embeddings are 1024-d and indexed with HNSW."""

    __tablename__ = "memory_facts"
    __table_args__ = (
        CheckConstraint(f"scope IN {_SCOPES}", name="scope"),
        CheckConstraint(f"category IN {_CATEGORIES}", name="category"),
        CheckConstraint(f"source_kind IN {_SOURCES}", name="source_kind"),
        CheckConstraint(f"trust_level IN {_TRUST}", name="trust_level"),
        CheckConstraint(f"status IN {_STATUS}", name="status"),
        CheckConstraint("length(content) <= 1000", name="content_len"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint(
            "(scope = 'user' AND user_id IS NOT NULL) "
            "OR (scope = 'agent' AND agent_id IS NOT NULL) "
            "OR (scope = 'team' AND team_id IS NOT NULL) "
            "OR (scope = 'agent_user' AND agent_id IS NOT NULL AND user_id IS NOT NULL)",
            name="scope_shape",
        ),
        Index(
            "ix_memory_user",
            "tenant_id",
            "user_id",
            postgresql_where=sql_text("status = 'active'"),
        ),
        Index(
            "ix_memory_agent",
            "tenant_id",
            "agent_id",
            postgresql_where=sql_text("status = 'active'"),
        ),
        Index(
            "ix_memory_team",
            "tenant_id",
            "team_id",
            postgresql_where=sql_text("status = 'active'"),
        ),
        Index(
            "ix_memory_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=sql_text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'fact'"))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    embedding_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL")
    )
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    trust_level: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'high'")
    )
    confidence: Mapped[float] = mapped_column(REAL, nullable=False, server_default=sql_text("1.0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'active'"))
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_facts.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recall_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
