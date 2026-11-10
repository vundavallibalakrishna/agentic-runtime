"""Guest sign-in, pack flags, personal export and the audit export.

The records desk is a pack. These routes stay because they are platform features:
signing a guest in, enabling a pack, exporting one person's rows, and reading the
security audit export.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_common.errors import UnauthenticatedError
from ar_contracts.api_model import ApiModel
from ar_domain.agents.access import Actor
from ar_domain.identity.guests import GuestBook, open_agent_turn

router = APIRouter()


class GuestTurnBody(ApiModel):
    text: str


@router.post("/api/v1/guest/agents/{agent_id}/turns")
@expose(public=False, permission=None)
async def guest_agent_turn(
    agent_id: uuid.UUID, body: GuestTurnBody, request: Request
) -> dict[str, object]:
    principal = getattr(request.state, "principal", None)
    if principal is None or getattr(principal, "kind", "") != "guest":
        raise UnauthenticatedError()
    person = Actor(
        tenant_id=uuid.UUID(str(principal.tenant_id)),
        user_id=uuid.UUID(str(principal.id)),
        permissions=frozenset(),
        kind="guest",
    )
    return open_agent_turn(chat(request), person, agent_id, body.text)


class GuestLinkBody(ApiModel):
    email: str


class GuestSessionBody(ApiModel):
    token: str
    totp: str = ""


@router.post("/api/v1/auth/guest/request-link")
@expose(public=True, permission=None)
async def request_link(body: GuestLinkBody, request: Request) -> Response:
    GuestBook(chat(request)).request_link(body.email)
    return Response(status_code=202)


@router.post("/api/v1/auth/guest/session")
@expose(public=True, permission=None)
async def guest_session(body: GuestSessionBody, request: Request) -> Response:
    opened = GuestBook(chat(request)).session(body.token, body.totp)
    response = JSONResponse(opened)
    response.set_cookie(
        "ar_guest_session",
        str(opened["session_id"]),
        httponly=True,
        samesite="lax",
        path="/guest",
        secure=False,
    )
    return response


@router.post("/api/v1/auth/guest/totp/enroll")
@expose(public=False, permission=None)
async def enroll_totp(request: Request) -> dict[str, str]:
    session_id = request.cookies.get("ar_guest_session", "")
    if not session_id:
        session_id = request.headers.get("x-guest-session", "")
    return GuestBook(chat(request)).enroll(session_id)


@router.get("/api/v1/tenant/packs")
@expose(public=False, permission=None)
async def list_tenant_packs(request: Request) -> dict[str, object]:
    from ar_domain.packs.registry import tenant_packs  # noqa: PLC0415

    return page(tenant_packs(chat(request), actor(request)))


@router.post(
    "/api/v1/tenant/packs/{pack_id}:enable",
    dependencies=[Depends(require_permission("packs:manage"))],
)
@expose(public=False, permission="packs:manage")
async def enable_pack(pack_id: str, request: Request) -> dict[str, object]:
    from ar_domain.packs.registry import set_enabled  # noqa: PLC0415

    return set_enabled(chat(request), actor(request), pack_id, enabled=True)


@router.post(
    "/api/v1/tenant/packs/{pack_id}:disable",
    dependencies=[Depends(require_permission("packs:manage"))],
)
@expose(public=False, permission="packs:manage")
async def disable_pack(pack_id: str, request: Request) -> dict[str, object]:
    from ar_domain.packs.registry import set_enabled  # noqa: PLC0415

    return set_enabled(chat(request), actor(request), pack_id, enabled=False)


@router.get("/api/v1/me/export")
@expose(public=False, permission=None)
async def export_me(request: Request) -> dict[str, object]:
    from ar_domain.identity.data_rights import export_user  # noqa: PLC0415

    return export_user(chat(request), actor(request))


@router.post(
    "/api/v1/users/{user_id}:erase",
    dependencies=[Depends(require_permission("users:manage"))],
)
@expose(public=False, permission="users:manage")
async def erase_user(user_id: uuid.UUID, request: Request) -> dict[str, object]:
    from ar_domain.identity.erasure import erase_user as erase  # noqa: PLC0415

    return erase(chat(request), actor(request), user_id)


@router.post("/api/v1/audit-exports", dependencies=[Depends(require_permission("audit:export"))])
@expose(public=False, permission="audit:export")
async def create_audit_export(request: Request) -> dict[str, object]:
    from ar_domain.audit.exports import AuditExportBook  # noqa: PLC0415

    return AuditExportBook(chat(request)).start(actor(request))


@router.get(
    "/api/v1/audit-exports/{export_id}",
    dependencies=[Depends(require_permission("audit:read"))],
)
@expose(public=False, permission="audit:read")
async def get_audit_export(export_id: uuid.UUID, request: Request) -> dict[str, object]:
    from ar_domain.audit.exports import AuditExportBook  # noqa: PLC0415

    return AuditExportBook(chat(request)).get(actor(request), export_id)
