"""Knowledge HTTP surface. Spec: docs/03-specs/10-knowledge.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.knowledge.book import KnowledgeBook

router = APIRouter()


class CollectionBody(ApiModel):
    slug: str = ""
    name: str = ""
    description: str = ""
    visibility: str = "tenant"
    owner_team_id: uuid.UUID | None = None
    acl_mode: str = "source"
    sensitivity: str = "normal"
    classification: str = "internal"
    embedding_alias: str = "embed"
    text_search_config: str = "simple"
    chunking: dict[str, object] | None = None
    dims: int = 1024


class CollectionPatch(ApiModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None
    owner_team_id: uuid.UUID | None = None
    sensitivity: str | None = None
    classification: str | None = None


class SourceBody(ApiModel):
    name: str = ""
    kind: str = ""
    config: dict[str, object] | None = None
    secret_id: uuid.UUID | None = None
    data_connection_id: uuid.UUID | None = None
    sync_schedule: str | None = None
    acl_sync_schedule: str | None = None


class SourcePatch(ApiModel):
    name: str | None = None
    config: dict[str, object] | None = None
    sync_schedule: str | None = None


class DocumentBody(ApiModel):
    file_ids: list[uuid.UUID] = Field(default_factory=list)
    acl_principals: list[str] | None = None


class SyncBody(ApiModel):
    mode: str = "incremental"


class ReindexBody(ApiModel):
    embedding_alias: str | None = None
    chunking: dict[str, object] | None = None
    text_search_config: str | None = None
    target_backend: str | None = None


class SearchBody(ApiModel):
    query: str = ""
    collection_ids: list[uuid.UUID] = Field(default_factory=list)
    top_k: int = 8
    debug: bool = False


def _book(request: Request) -> KnowledgeBook:
    return KnowledgeBook(chat(request))


@router.get(
    "/api/v1/knowledge/collections",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def list_collections(request: Request) -> dict[str, object]:
    return page(_book(request).list_collections(actor(request)))


@router.post(
    "/api/v1/knowledge/collections",
    dependencies=[Depends(require_permission("knowledge:manage"))],
)
@expose(public=False, permission="knowledge:manage")
async def create_collection(body: CollectionBody, request: Request) -> dict[str, object]:
    return _book(request).create_collection(actor(request), dump(body))


@router.get(
    "/api/v1/knowledge/collections/{collection_id}",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def get_collection(collection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get_collection(actor(request), collection_id)


@router.patch(
    "/api/v1/knowledge/collections/{collection_id}",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def patch_collection(
    collection_id: uuid.UUID, body: CollectionPatch, request: Request
) -> dict[str, object]:
    return _book(request).patch_collection(actor(request), collection_id, dump(body))


@router.delete(
    "/api/v1/knowledge/collections/{collection_id}",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def delete_collection(collection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).delete_collection(actor(request), collection_id)


@router.post(
    "/api/v1/knowledge/collections/{collection_id}:reindex",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def reindex_collection(
    collection_id: uuid.UUID, body: ReindexBody, request: Request
) -> dict[str, object]:
    return _book(request).reindex_collection(actor(request), collection_id, dump(body))


@router.get(
    "/api/v1/knowledge/collections/{collection_id}/sources",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def list_sources(collection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_book(request).list_sources(actor(request), collection_id))


@router.post(
    "/api/v1/knowledge/collections/{collection_id}/sources",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def create_source(
    collection_id: uuid.UUID, body: SourceBody, request: Request
) -> dict[str, object]:
    return _book(request).create_source(actor(request), collection_id, dump(body))


@router.get(
    "/api/v1/knowledge/sources/{source_id}",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def get_source(source_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get_source(actor(request), source_id)


@router.patch(
    "/api/v1/knowledge/sources/{source_id}",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def patch_source(
    source_id: uuid.UUID, body: SourcePatch, request: Request
) -> dict[str, object]:
    return _book(request).patch_source(actor(request), source_id, dump(body))


@router.delete(
    "/api/v1/knowledge/sources/{source_id}",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def delete_source(source_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).delete_source(actor(request), source_id)


@router.post(
    "/api/v1/knowledge/sources/{source_id}:test",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def test_source(source_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).test_source(actor(request), source_id)


@router.post(
    "/api/v1/knowledge/sources/{source_id}:sync",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def sync_source(source_id: uuid.UUID, body: SyncBody, request: Request) -> dict[str, object]:
    return _book(request).sync(actor(request), source_id, body.mode)


@router.post(
    "/api/v1/knowledge/sources/{source_id}:pause",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def pause_source(source_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).pause(actor(request), source_id)


@router.post(
    "/api/v1/knowledge/sources/{source_id}:resume",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def resume_source(source_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).resume(actor(request), source_id)


@router.get(
    "/api/v1/knowledge/collections/{collection_id}/documents",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def list_documents(
    collection_id: uuid.UUID,
    request: Request,
    q: Annotated[str, Query()] = "",
    status: Annotated[str, Query()] = "",
    source_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    return page(
        _book(request).list_documents(
            actor(request), collection_id, query=q, status=status, source_id=source_id
        )
    )


@router.post(
    "/api/v1/knowledge/collections/{collection_id}/documents",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def add_documents(
    collection_id: uuid.UUID, body: DocumentBody, request: Request
) -> dict[str, object]:
    return await _book(request).add_documents(actor(request), collection_id, dump(body))


@router.get(
    "/api/v1/knowledge/documents/{document_id}",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def get_document(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get_document(actor(request), document_id)


@router.get(
    "/api/v1/knowledge/documents/{document_id}/chunks",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def document_chunks(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_book(request).chunks(actor(request), document_id))


@router.post(
    "/api/v1/knowledge/documents/{document_id}:reingest",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def reingest_document(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return await _book(request).reingest(actor(request), document_id)


@router.delete(
    "/api/v1/knowledge/documents/{document_id}",
    status_code=202,
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def delete_document(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).remove_document(actor(request), document_id)


@router.get(
    "/api/v1/knowledge/collections/{collection_id}/jobs",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def list_jobs(collection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_book(request).list_jobs(actor(request), collection_id))


@router.get(
    "/api/v1/knowledge/jobs/{job_id}",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def get_job(job_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get_job(actor(request), job_id)


@router.post(
    "/api/v1/knowledge/jobs/{job_id}:cancel",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def cancel_job(job_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).cancel_job(actor(request), job_id)


@router.post(
    "/api/v1/knowledge/search",
    dependencies=[Depends(require_permission("knowledge:read"))],
)
@expose(public=False, permission="knowledge:read")
async def search(body: SearchBody, request: Request) -> dict[str, object]:
    return _book(request).search(actor(request), dump(body))
