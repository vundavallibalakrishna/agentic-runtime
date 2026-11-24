"""Document library HTTP surface."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_contracts.api_model import ApiModel
from ar_domain.documents.library import DocumentLibrary, ingest_bytes

router = APIRouter()


class RuleSetItem(ApiModel):
    item_id: str = ""
    statement: str = ""


class RuleSetBody(ApiModel):
    id: str = ""
    version: str = ""
    items: list[RuleSetItem] = Field(default_factory=list)
    source_file_id: uuid.UUID | None = None
    sha256: str = ""


def _library(request: Request) -> DocumentLibrary:
    return DocumentLibrary(chat(request))


@router.get(
    "/api/v1/library-documents",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_library_documents(request: Request) -> dict[str, object]:
    listed = _library(request).list_items(actor(request))
    rows = listed.get("documents") if isinstance(listed, dict) else listed
    return page(rows if isinstance(rows, list) else [])


@router.post(
    "/api/v1/library-documents",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def upload_library_document(
    request: Request,
    upload: Annotated[UploadFile, File()],
) -> dict[str, object]:
    data = await upload.read()
    return await ingest_bytes(
        chat(request),
        actor(request),
        data=data,
        filename=upload.filename or "upload",
        media_type=upload.content_type or "",
        source="upload",
    )


class ReprocessBody(ApiModel):
    engine: str = ""


@router.delete(
    "/api/v1/library-documents/{document_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def delete_library_document(document_id: uuid.UUID, request: Request) -> dict[str, bool]:
    from ar_domain.documents.lifecycle import delete_library  # noqa: PLC0415

    delete_library(chat(request), actor(request), document_id)
    return {"deleted": True}


@router.post(
    "/api/v1/library-documents/{document_id}:reprocess",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def reprocess_library_document(
    document_id: uuid.UUID, body: ReprocessBody, request: Request
) -> dict[str, object]:
    from ar_domain.documents.lifecycle import reprocess_document  # noqa: PLC0415

    return await reprocess_document(chat(request), actor(request), document_id, engine=body.engine)


@router.get(
    "/api/v1/library-documents/{document_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def get_library_document(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).get(actor(request), document_id)


@router.get(
    "/api/v1/library-documents/{document_id}/passages",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_passages(
    document_id: uuid.UUID,
    request: Request,
    page_from: Annotated[int, Query(alias="pageFrom")] = 1,
    page_to: Annotated[int, Query(alias="pageTo")] = 0,
) -> dict[str, object]:
    return _library(request).passages(
        actor(request), document_id, page_from=page_from, page_to=page_to
    )


@router.get(
    "/api/v1/library-documents/{document_id}/diff",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def diff_documents(
    document_id: uuid.UUID,
    request: Request,
    other: Annotated[uuid.UUID, Query(alias="otherDocumentId")],
) -> dict[str, object]:
    """The sections that differ between this document and another. No model is asked."""
    return _library(request).diff(actor(request), document_id, other)


@router.get(
    "/api/v1/library-documents/{document_id}/outline",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def document_outline(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).outline(actor(request), document_id)


@router.get(
    "/api/v1/library-documents/{document_id}/tables",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def document_tables(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).tables(actor(request), document_id)


@router.post(
    "/api/v1/rule-sets",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def import_rule_set_route(body: RuleSetBody, request: Request) -> dict[str, object]:
    from ar_domain.documents.rules import import_rule_set  # noqa: PLC0415

    return import_rule_set(chat(request), actor(request), body.model_dump(by_alias=False))


@router.get(
    "/api/v1/rule-sets/{rule_set_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def export_rule_set_route(
    rule_set_id: str,
    request: Request,
    version: Annotated[str, Query()] = "",
) -> dict[str, object]:
    from ar_domain.documents.rules import export_rule_set  # noqa: PLC0415

    return export_rule_set(chat(request), actor(request), rule_set_id, version)
