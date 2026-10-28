"""Audit, reporting, inspection and privacy routes under `/api/v1/ext/grc`."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request, Response

from ar_api.deps import expose
from ar_api.routers.tooling import actor, chat
from ar_common.errors import NotFoundError
from ar_pack_grc import inspections, pbc, privacy, reports, resilience
from ar_pack_grc.access import pack_enabled, require_enabled

router = APIRouter()


def _caller(request: Request, *permissions: str) -> Any:
    who = actor(request)
    require_enabled(chat(request), who, *permissions)
    return who


def _guest_or(request: Request, *permissions: str) -> Any:
    who = actor(request)
    if not pack_enabled(chat(request), who.tenant_id):
        raise NotFoundError()
    if who.kind == "guest":
        return who
    return _caller(request, *permissions)


@router.get("/pbc-requests")
@expose(public=False, permission="grc.audit_portal:manage")
async def list_pbc(request: Request) -> dict[str, Any]:
    who = actor(request)
    if not pack_enabled(chat(request), who.tenant_id):
        raise NotFoundError()
    return pbc.list_requests(chat(request), who)


@router.post("/pbc-requests")
@expose(public=False, permission="grc.audit_portal:manage")
async def create_pbc(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return pbc.create_request(chat(request), _caller(request, "grc.audit_portal:manage"), body)


@router.patch("/pbc-requests/{request_id}")
@expose(public=False, permission="grc.audit_portal:manage")
async def patch_pbc(
    request_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return pbc.update_request(
        chat(request), _guest_or(request, "grc.audit_portal:manage"), request_id, body
    )


@router.get("/pbc-requests/{request_id}/response")
@expose(public=False, permission="grc.audit_portal:manage")
async def pbc_response(request_id: uuid.UUID, request: Request) -> Response:
    who = actor(request)
    if not pack_enabled(chat(request), who.tenant_id):
        raise NotFoundError()
    data = pbc.response_pdf(chat(request), who, request_id)
    return Response(content=data, media_type="application/pdf")


@router.post("/pbc-lists:import")
@expose(public=False, permission="grc.audit_portal:manage")
async def import_pbc(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return pbc.import_list(chat(request), _caller(request, "grc.audit_portal:manage"), body)


@router.get("/report-templates")
@expose(public=False, permission="grc.reports:export")
async def list_report_templates(request: Request) -> dict[str, Any]:
    return reports.list_templates(chat(request), _caller(request, "grc.reports:export"))


@router.post("/reports:render", status_code=202)
@expose(public=False, permission="grc.reports:export")
async def render_report(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return reports.render(chat(request), _caller(request, "grc.reports:export"), body)


@router.get("/inspections")
@expose(public=False, permission="grc.inspections:manage")
async def list_inspections(request: Request) -> dict[str, Any]:
    return inspections.list_inspections(chat(request), _caller(request, "grc.inspections:manage"))


@router.post("/inspections")
@expose(public=False, permission="grc.inspections:manage")
async def open_inspection(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return inspections.open_inspection(
        chat(request), _caller(request, "grc.inspections:manage"), body
    )


@router.get("/dsar-requests")
@expose(public=False, permission="grc.privacy:manage")
async def list_dsar(request: Request) -> dict[str, Any]:
    return privacy.list_requests(chat(request), _caller(request, "grc.privacy:manage"))


@router.post("/dsar-requests")
@expose(public=False, permission="grc.privacy:manage")
async def create_dsar(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return privacy.create_request(chat(request), _caller(request, "grc.privacy:manage"), body)


@router.post("/dsar-requests/{request_id}:fulfil")
@expose(public=False, permission="grc.privacy:manage")
async def fulfil_dsar(request_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return privacy.fulfil(chat(request), _caller(request, "grc.privacy:manage"), request_id)


@router.get("/consent-records")
@expose(public=False, permission="grc.privacy:manage")
async def list_consent(request: Request) -> dict[str, Any]:
    return privacy.list_consent(chat(request), _caller(request, "grc.privacy:manage"))


@router.post("/consent-records")
@expose(public=False, permission="grc.privacy:manage")
async def create_consent(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return privacy.record_consent(chat(request), _caller(request, "grc.privacy:manage"), body)


@router.get("/resilience-tests")
@expose(public=False, permission="grc.controls:read")
async def list_resilience(request: Request) -> dict[str, Any]:
    return resilience.list_tests(chat(request), _caller(request, "grc.controls:read"))


@router.post("/resilience-tests")
@expose(public=False, permission="grc.controls:manage")
async def create_resilience(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return resilience.record_test(chat(request), _caller(request, "grc.controls:manage"), body)
