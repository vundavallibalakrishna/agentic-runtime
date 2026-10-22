"""Bundle import and export. Spec: docs/03-specs/05-agent-registry.md §3."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from ar_api.actors import actor_from, chat_of, principal_of
from ar_api.deps import expose, require_permission
from ar_contracts.api_model import ApiModel
from ar_domain.bundles.export import export_bundle, to_yaml
from ar_domain.bundles.import_ import import_bundle

router = APIRouter()


class ImportBody(ApiModel):
    bundle: dict[str, Any] | None = None
    yaml_text: str | None = None
    dry_run: bool = False


@router.get("/api/v1/bundles:export", dependencies=[Depends(require_permission("agents:read"))])
@expose(public=False, permission="agents:read")
async def export_agents(
    request: Request,
    ids: Annotated[str | None, Query()] = None,
) -> Response:
    actor = actor_from(principal_of(request))
    selected = None if not ids else [uuid.UUID(item) for item in ids.split(",") if item]
    document = export_bundle(chat_of(request), actor, ids=selected)
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse(document)
    return Response(to_yaml(document), media_type="application/yaml")


@router.post("/api/v1/bundles:import", dependencies=[Depends(require_permission("agents:create"))])
@expose(public=False, permission="agents:create")
async def import_agents(body: ImportBody, request: Request) -> dict[str, object]:
    payload: object = body.yaml_text if body.yaml_text else body.bundle
    return import_bundle(
        chat_of(request),
        actor_from(principal_of(request)),
        payload or {},
        dry_run=body.dry_run,
    )
