"""Knowledge tables. Spec: docs/04-data/schema.md §8."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    literal_column,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, REGCONFIG, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_domain.db.base import Base
from ar_domain.db.types import created_at_col, jsonb_col, text_array, updated_at_col, uuid_pk

_CLASS = "('public','internal','confidential','restricted')"
_DIMS = (384, 768, 1024, 1536, 3072)


def _hnsw(dim: int) -> Index:
    expression = f"(embedding::halfvec({dim}))"
    return Index(
        f"ix_chunk_emb_hnsw_{dim}",
        sql_text(expression),
        postgresql_using="hnsw",
        postgresql_ops={expression: "halfvec_cosine_ops"},
        postgresql_where=sql_text(f"dims = {dim}"),
        postgresql_with={"m": 16, "ef_construction": 64},
    )


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"
    __table_args__ = (
        CheckConstraint("visibility IN ('private','team','tenant')", name="visibility"),
        CheckConstraint("acl_mode IN ('source','collection')", name="acl_mode"),
        CheckConstraint("sensitivity IN ('normal','high')", name="sensitivity"),
        CheckConstraint(f"classification IN {_CLASS}", name="classification"),
        CheckConstraint("store_backend IN ('pgvector','qdrant')", name="store_backend"),
        CheckConstraint("text_search_config IN ('simple','english')", name="text_search_config"),
        UniqueConstraint("tenant_id", "slug", name="uq_knowledge_collections_slug"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("''"))
    owner_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL")
    )
    visibility: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'tenant'")
    )
    acl_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'source'"))
    sensitivity: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'normal'")
    )
    classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'internal'")
    )
    embedding_alias: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'embed'")
    )
    embedding_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL")
    )
    index_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sql_text("1")
    )
    store_backend: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'pgvector'")
    )
    store_collection: Mapped[str] = mapped_column(Text, nullable=False)
    text_search_config: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'simple'")
    )
    chunking: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=literal_column(
            """'{"target_tokens":512,"overlap_pct":12,"contextual":false}'::jsonb"""
        ),
    )
    stats: Mapped[dict[str, object]] = jsonb_col()
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('upload','web','s3','sharepoint','confluence','google_drive',"
            "'database','mcp_resource')",
            name="kind",
        ),
        CheckConstraint("status IN ('active','paused','error')", name="status"),
        Index("ix_knowledge_sources_collection", "tenant_id", "collection_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, object]] = jsonb_col()
    secret_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret_refs.id", ondelete="RESTRICT")
    )
    data_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_connections.id", ondelete="RESTRICT")
    )
    sync_schedule: Mapped[str | None] = mapped_column(Text)
    acl_sync_schedule: Mapped[str | None] = mapped_column(Text)
    temporal_schedule_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'active'"))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(Text)
    cursor: Mapped[dict[str, object]] = jsonb_col()
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"classification IN {_CLASS}", name="classification"),
        CheckConstraint(
            "status IN ('pending','parsing','embedding','indexed','failed','deleted')",
            name="status",
        ),
        UniqueConstraint("source_id", "external_id", name="uq_documents_source_external"),
        Index("ix_documents_collection", "tenant_id", "collection_id", "status"),
        Index(
            "ix_documents_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    version_hash: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=sql_text("0")
    )
    language: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sql_text("'internal'")
    )
    acl_principals: Mapped[list[str]] = text_array()
    acl_hash: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("''"))
    raw_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", name="fk_documents_raw", ondelete="SET NULL")
    )
    parsed_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", name="fk_documents_parsed", ondelete="SET NULL")
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'pending'"))
    error: Mapped[str | None] = mapped_column(Text)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "ordinal", "index_version", name="uq_document_chunks_ordinal"
        ),
        Index("ix_document_chunks_doc", "tenant_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    context_prefix: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("''"))
    heading_path: Mapped[list[str]] = text_array()
    page_from: Mapped[int | None] = mapped_column(Integer)
    page_to: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        CheckConstraint(f"classification IN {_CLASS}", name="classification"),
        CheckConstraint(f"dims IN {_DIMS}", name="dims"),
        CheckConstraint("vector_dims(embedding) = dims", name="vector_dims"),
        Index("ix_chunk_emb_target", "tenant_id", "collection_id", "index_version"),
        Index("ix_chunk_emb_document", "document_id"),
        Index("ix_chunk_emb_acl", "acl", postgresql_using="gin"),
        Index("ix_chunk_emb_tsv", "tsv", postgresql_using="gin"),
        *tuple(_hnsw(dim) for dim in _DIMS),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    index_version: Mapped[int] = mapped_column(Integer, nullable=False)
    acl: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    dims: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(HALFVEC(), nullable=False)
    text_search_config: Mapped[str] = mapped_column(
        REGCONFIG, nullable=False, server_default=sql_text("'simple'")
    )
    lexical_text: Mapped[str] = mapped_column(Text, nullable=False)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector(text_search_config, lexical_text)", persisted=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = created_at_col()


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('full_sync','incremental_sync','acl_sync','reindex','single_document')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','partially_failed','failed','cancelled')",
            name="status",
        ),
        CheckConstraint(
            "triggered_by IN ('schedule','manual','webhook','upload','system')",
            name="triggered_by",
        ),
        Index(
            "ix_ingestion_jobs_source",
            "tenant_id",
            "source_id",
            sql_text("created_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE")
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'queued'"))
    temporal_workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    stats: Mapped[dict[str, object]] = jsonb_col()
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
