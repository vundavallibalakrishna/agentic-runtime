"""OpenAPI import and tools described in plain language."""

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump
from ar_contracts.api_model import ApiModel
from ar_domain.tools.imports import ToolImporter

router = APIRouter()


class OpenApiPreview(ApiModel):
    document: dict[str, object] | str | None = None
    url: str = ""
    base_url: str = ""


class OpenApiImport(ApiModel):
    slug: str
    name: str = ""
    description: str = ""
    document: dict[str, object] | str | None = None
    url: str = ""
    base_url: str = ""
    operations: list[str] = Field(default_factory=list)
    connection: str = ""


class DescribeBody(ApiModel):
    description: str = ""
    name: str = ""
    slug: str = ""
    method: str = ""
    url: str = ""
    connection: str = ""
    parameters: list[str] = Field(default_factory=list)
    returns: str = ""
    title: str = ""


def _importer(request: Request) -> ToolImporter:
    return ToolImporter(chat(request))


@router.post(
    "/api/v1/openapi-imports:preview",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def preview_openapi(body: OpenApiPreview, request: Request) -> dict[str, object]:
    return _importer(request).preview_openapi(dump(body))


@router.post(
    "/api/v1/openapi-imports",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def import_openapi(body: OpenApiImport, request: Request) -> dict[str, object]:
    return _importer(request).import_openapi(actor(request), dump(body))


@router.post(
    "/api/v1/described-tools:preview",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def preview_described_tool(body: DescribeBody, request: Request) -> dict[str, object]:
    return _importer(request).preview_description(dump(body))


@router.post(
    "/api/v1/described-tools",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def save_described_tool(body: DescribeBody, request: Request) -> dict[str, object]:
    return _importer(request).save_description(actor(request), dump(body))
