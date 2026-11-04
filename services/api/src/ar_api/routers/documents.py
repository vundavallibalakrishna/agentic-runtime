"""Document library HTTP surface."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_contracts.api_model import ApiModel
from ar_domain.documents.library import DocumentLibrary

router = APIRouter()


class CompareBody(ApiModel):
    other_document_id: uuid.UUID
    model_alias: str = ""


class LibraryCheckBody(ApiModel):
    standard_document_id: uuid.UUID | None = None
    requirements: list[str] = Field(default_factory=list)
    label: str = ""
    model_alias: str = ""


class GapsBody(ApiModel):
    standard_document_id: uuid.UUID | None = None
    requirements: list[str] = Field(default_factory=list)
    model_alias: str = ""


class ExtractBody(ApiModel):
    fields: list[str] = Field(default_factory=list)
    model_alias: str = ""


class RewriteBody(ApiModel):
    anchor: str = ""
    instruction: str
    model_alias: str = ""


class DecideBody(ApiModel):
    decision: str
    hunk_id: str = ""


class SummariseBody(ApiModel):
    model_alias: str = ""


def _library(request: Request) -> DocumentLibrary:
    return DocumentLibrary(chat(request))


@router.get(
    "/api/v1/library-documents",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_library_documents(request: Request) -> dict[str, object]:
    return page(_library(request).list_items(actor(request)))


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
    return _library(request).ingest(
        actor(request),
        data=data,
        filename=upload.filename or "upload",
        media_type=upload.content_type or "",
        source="upload",
    )


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
    "/api/v1/library-documents/{document_id}:summarise",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def summarise_document(
    document_id: uuid.UUID, body: SummariseBody, request: Request
) -> dict[str, object]:
    return _library(request).summarise(actor(request), document_id, alias=body.model_alias)


@router.post(
    "/api/v1/library-documents/{document_id}:compare",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def compare_documents(
    document_id: uuid.UUID, body: CompareBody, request: Request
) -> dict[str, object]:
    return _library(request).compare(
        actor(request), document_id, body.other_document_id, alias=body.model_alias
    )


@router.post(
    "/api/v1/library-documents/{document_id}:check",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def check_document(
    document_id: uuid.UUID, body: LibraryCheckBody, request: Request
) -> dict[str, object]:
    return _library(request).check(
        actor(request),
        document_id,
        requirements=body.requirements,
        standard_id=body.standard_document_id,
        label=body.label,
        alias=body.model_alias,
    )


@router.post(
    "/api/v1/library-documents/{document_id}:gaps",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def document_gaps(
    document_id: uuid.UUID, body: GapsBody, request: Request
) -> dict[str, object]:
    return _library(request).gaps(
        actor(request),
        document_id,
        requirements=body.requirements,
        standard_id=body.standard_document_id,
        alias=body.model_alias,
    )


@router.post(
    "/api/v1/library-documents/{document_id}:redact",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def redact_document(document_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).redact(actor(request), document_id)


@router.post(
    "/api/v1/library-documents/{document_id}:extract",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def extract_document_fields(
    document_id: uuid.UUID, body: ExtractBody, request: Request
) -> dict[str, object]:
    return _library(request).extract(
        actor(request), document_id, body.fields, alias=body.model_alias
    )


@router.post(
    "/api/v1/library-documents/{document_id}:rewrite",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def rewrite_document(
    document_id: uuid.UUID, body: RewriteBody, request: Request
) -> dict[str, object]:
    return _library(request).propose_rewrite(
        actor(request),
        document_id,
        anchor=body.anchor,
        instruction=body.instruction,
        alias=body.model_alias,
    )


@router.get(
    "/api/v1/document-checks/{check_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def get_document_check(check_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).get_check(actor(request), check_id)


@router.get(
    "/api/v1/document-comparisons/{comparison_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def get_document_comparison(comparison_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).get_comparison(actor(request), comparison_id)


@router.get(
    "/api/v1/document-rewrites/{rewrite_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def get_document_rewrite(rewrite_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _library(request).get_rewrite(actor(request), rewrite_id)


@router.post(
    "/api/v1/document-rewrites/{rewrite_id}:decide",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def decide_document_rewrite(
    rewrite_id: uuid.UUID, body: DecideBody, request: Request
) -> dict[str, object]:
    return _library(request).decide_rewrite(
        actor(request), rewrite_id, decision=body.decision, hunk_id=body.hunk_id
    )
