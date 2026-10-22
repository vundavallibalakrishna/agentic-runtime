"""Sandbox templates and computers. Spec: docs/03-specs/12-sandbox-manager.md §6."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.sandboxes.service import SandboxBook

router = APIRouter()


class TemplateBody(ApiModel):
    slug: str = ""
    name: str = ""
    image_ref: str = ""
    runtime_class: str = "gvisor"
    cpu_millis: int = 2000
    memory_mb: int = 4096
    disk_gb: int = 10
    allow_browser: bool = False
    allow_packages: bool = False
    egress_allowlist: list[str] = Field(default_factory=list)
    max_classification: str = "confidential"
    idle_suspend_s: int = 900
    max_lifetime_s: int = 86400
    exec_timeout_s: int = 120
    retention_days: int = 7


class TemplatePatch(ApiModel):
    name: str | None = None
    image_ref: str | None = None
    runtime_class: str | None = None
    cpu_millis: int | None = None
    memory_mb: int | None = None
    disk_gb: int | None = None
    allow_browser: bool | None = None
    allow_packages: bool | None = None
    egress_allowlist: list[str] | None = None
    max_classification: str | None = None
    idle_suspend_s: int | None = None
    max_lifetime_s: int | None = None
    exec_timeout_s: int | None = None
    retention_days: int | None = None
    status: str | None = None


class ExportBody(ApiModel):
    path: str = ""
    name: str = ""


def _book(request: Request) -> SandboxBook:
    return SandboxBook(chat(request))


@router.get(
    "/api/v1/sandbox-templates", dependencies=[Depends(require_permission("sandboxes:manage"))]
)
@expose(public=False, permission="sandboxes:manage")
async def list_templates(request: Request) -> dict[str, object]:
    return page(_book(request).list_templates(actor(request)))


@router.post(
    "/api/v1/sandbox-templates", dependencies=[Depends(require_permission("sandboxes:manage"))]
)
@expose(public=False, permission="sandboxes:manage")
async def create_template(body: TemplateBody, request: Request) -> dict[str, object]:
    return _book(request).create_template(actor(request), dump(body))


@router.patch(
    "/api/v1/sandbox-templates/{template_id}",
    dependencies=[Depends(require_permission("sandboxes:manage"))],
)
@expose(public=False, permission="sandboxes:manage")
async def patch_template(
    template_id: uuid.UUID, body: TemplatePatch, request: Request
) -> dict[str, object]:
    return _book(request).patch_template(actor(request), template_id, dump(body))


@router.delete(
    "/api/v1/sandbox-templates/{template_id}",
    dependencies=[Depends(require_permission("sandboxes:manage"))],
)
@expose(public=False, permission="sandboxes:manage")
async def delete_template(template_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _book(request).delete_template(actor(request), template_id)
    return {"deleted": True}


@router.get("/api/v1/sandboxes", dependencies=[Depends(require_permission("sandboxes:manage"))])
@expose(public=False, permission="sandboxes:manage")
async def list_sandboxes(request: Request) -> dict[str, object]:
    return page(_book(request).list_sandboxes(actor(request)))


@router.get(
    "/api/v1/sandboxes/{sandbox_id}", dependencies=[Depends(require_permission("chat:use"))]
)
@expose(public=False, permission="chat:use")
async def get_sandbox(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get_sandbox(actor(request), sandbox_id)


@router.post(
    "/api/v1/sandboxes/{sandbox_id}:terminate",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def terminate_sandbox(sandbox_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).terminate(actor(request), sandbox_id)


@router.get(
    "/api/v1/conversations/{conversation_id}/sandbox",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def conversation_sandbox(conversation_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).conversation_sandbox(actor(request), conversation_id)


@router.get(
    "/api/v1/sandboxes/{sandbox_id}/files",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_sandbox_files(
    sandbox_id: uuid.UUID,
    request: Request,
    path: Annotated[str, Query()] = "/workspace",
) -> dict[str, object]:
    return page(_book(request).files(actor(request), sandbox_id, path))


@router.get(
    "/api/v1/sandboxes/{sandbox_id}/files/content",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def sandbox_file_content(
    sandbox_id: uuid.UUID,
    request: Request,
    path: Annotated[str, Query()] = "/workspace",
) -> Response:
    data, headers = _book(request).file_bytes(actor(request), sandbox_id, path)
    media = headers.get("Content-Type", "application/octet-stream")
    return Response(content=data, media_type=media, headers=headers)


@router.post(
    "/api/v1/sandboxes/{sandbox_id}/files:export",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def export_sandbox_file(
    sandbox_id: uuid.UUID, body: ExportBody, request: Request
) -> dict[str, object]:
    from ar_domain.sandboxes.runtime import save_artifact  # noqa: PLC0415

    who = actor(request)
    row = _book(request).get_sandbox(who, sandbox_id)
    live = chat(request).sandboxes.get(uuid.UUID(str(row["id"])))
    result = save_artifact(
        chat(request),
        live if isinstance(live, dict) else {},
        body.path,
        body.name,
    )
    if result.get("is_error"):
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError(str(result.get("text") or "file not found"))
    structured = result.get("structured")
    return structured if isinstance(structured, dict) else {}
