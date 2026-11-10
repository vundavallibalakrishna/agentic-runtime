"""Postgres read model. The in-memory ``ChatService`` is a test double."""

from ar_domain.readmodel.boot import (
    MemoryStoreRefusedError,
    build_product_store,
    refuse_memory_double,
)
from ar_domain.readmodel.model import RepositoryReadModel

__all__ = [
    "MemoryStoreRefusedError",
    "RepositoryReadModel",
    "build_product_store",
    "refuse_memory_double",
]
