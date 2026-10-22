"""Content packs. Spec: docs/03-specs/05-agent-registry.md §10."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from ar_api.actors import actor_from, chat_of, principal_of
from ar_api.deps import expose, require_permission
from ar_contracts.api_model import ApiModel
from ar_domain.agents.packs import PackService

router = APIRouter()


class InstallBody(ApiModel):
    manifest: dict[str, Any]
    signature: str | None = None
    key_id: str | None = None


class UpgradeBody(InstallBody):
    accept_conflicts: bool = False


class UninstallBody(ApiModel):
    drop_schema: bool = False


def _packs(request: Request) -> PackService:
    return PackService(chat_of(request))


def _page(items: list[dict[str, object]]) -> dict[str, object]:
    return {"data": items}


@router.get("/api/v1/content-packs", dependencies=[Depends(require_permission("agents:read"))])
@expose(public=False, permission="agents:read")
async def list_packs(request: Request) -> dict[str, object]:
    return _page(_packs(request).list_packs(actor_from(principal_of(request))))


@router.post(
    "/api/v1/content-packs:install",
    dependencies=[Depends(require_permission("packs:manage"))],
)
@expose(public=False, permission="packs:manage")
async def install_pack(body: InstallBody, request: Request) -> dict[str, object]:
    return _packs(request).install(
        actor_from(principal_of(request)),
        body.manifest,
        signature=body.signature,
        key_id=body.key_id,
    )


@router.get(
    "/api/v1/content-packs/{pack_id}",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(public=False, permission="agents:read")
async def get_pack(pack_id: str, request: Request) -> dict[str, object]:
    return _packs(request).get(actor_from(principal_of(request)), pack_id)


@router.post(
    "/api/v1/content-packs/{pack_id}:upgrade",
    dependencies=[Depends(require_permission("packs:manage"))],
)
@expose(public=False, permission="packs:manage")
async def upgrade_pack(pack_id: str, body: UpgradeBody, request: Request) -> dict[str, object]:
    return _packs(request).upgrade(
        actor_from(principal_of(request)),
        pack_id,
        body.manifest,
        signature=body.signature,
        key_id=body.key_id,
        accept_conflicts=body.accept_conflicts,
    )


@router.post(
    "/api/v1/content-packs/{pack_id}:uninstall",
    dependencies=[Depends(require_permission("packs:manage"))],
)
@expose(public=False, permission="packs:manage")
async def uninstall_pack(pack_id: str, body: UninstallBody, request: Request) -> dict[str, object]:
    return _packs(request).uninstall(
        actor_from(principal_of(request)), pack_id, drop_schema=body.drop_schema
    )
