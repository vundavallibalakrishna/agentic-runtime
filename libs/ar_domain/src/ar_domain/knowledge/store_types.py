"""Retrieval store types. Spec: docs/03-specs/10-knowledge.md §6.2."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BackendName = Literal["pgvector", "qdrant"]
SUPPORTED_DIMS = frozenset({384, 768, 1024, 1536, 3072})
TEXT_CONFIGS = frozenset({"simple", "english"})
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoreCapabilities(_Frozen):
    native_sparse: bool
    transactional_with_pg: bool
    supported_dims: frozenset[int]


class PhysicalCollectionSpec(_Frozen):
    tenant_id: uuid.UUID
    collection_id: uuid.UUID
    isolation_tier: str = "shared"
    model_key: str
    dims: int


class IndexedChunk(_Frozen):
    chunk_id: uuid.UUID
    tenant_id: uuid.UUID
    collection_id: uuid.UUID
    document_id: uuid.UUID
    source_id: uuid.UUID
    index_version: int
    dense: list[float]
    lexical_text: str
    text_search_config: str = "simple"
    acl: list[str]
    classification: str
    mime_type: str = "text/markdown"
    title: str = ""
    language: str = ""
    modified_at: datetime | None = None


class DeleteFilter(_Frozen):
    tenant_id: uuid.UUID
    collection_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    index_version: int | None = None
    index_version_ne: int | None = None
    chunk_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def selector_present(self) -> DeleteFilter:
        if (
            self.collection_id is None
            and self.document_id is None
            and self.index_version is None
            and self.index_version_ne is None
            and not self.chunk_ids
        ):
            raise ValueError("delete filter needs a selector")
        return self


class SearchTarget(_Frozen):
    collection_id: uuid.UUID
    index_version: int
    store_collection: str
    text_search_config: str = "simple"


class HybridQuery(_Frozen):
    tenant_id: uuid.UUID
    text: str
    dense: list[float]
    targets: list[SearchTarget]
    principals: list[str]
    allowed_classifications: list[str]
    dense_k: int = 50
    lexical_k: int = 50
    fused_k: int = 50
    rrf_k: int = 60

    @model_validator(mode="after")
    def filters_present(self) -> HybridQuery:
        if not self.principals or not self.allowed_classifications:
            raise ValueError("principals and classifications are required")
        if not self.targets or len(self.targets) > 20:
            raise ValueError("search needs between 1 and 20 targets")
        return self


class ScoredChunk(_Frozen):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    collection_id: uuid.UUID
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None


class ExportedVector(_Frozen):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    index_version: int
    dense: list[float]


class StoreHealth(_Frozen):
    backend: str
    ok: bool
    latency_ms: float
    detail: str = ""
