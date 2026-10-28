"""Records, guests, governance and run records. Spec: docs/03-specs/21-records-governance.md."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.principal import content_hidden
from ar_api.routers.tooling import actor, chat, dump, page, stepped_up
from ar_common.errors import ArError, ErrorCode
from ar_common.time import utcnow
from ar_contracts.api_model import ApiModel
from ar_domain.agents.cards import GovernanceBook
from ar_domain.identity.guests import GuestBook
from ar_domain.identity.service import assert_step_up
from ar_domain.records.binders import BinderBook
from ar_domain.records.holds import HoldBook
from ar_domain.records.vault import EvidenceBook
from ar_domain.records.watermark import WatermarkError, watermark
from ar_domain.runs.records import RunRecordBook

router = APIRouter()


class EvidenceBody(ApiModel):
    file_id: uuid.UUID | None = None
    text: str = ""
    media_type: str = "text/plain"
    source_system: str = "api"
    collection_method: str = "api"
    provenance: dict[str, object] | None = None
    collector_run_id: uuid.UUID | None = None


class HoldBody(ApiModel):
    matter: str
    custodians: list[uuid.UUID] = Field(default_factory=list)
    scope_query: dict[str, object]
    approver_user_id: uuid.UUID


class ReleaseBody(ApiModel):
    reason: str


class ScheduleBody(ApiModel):
    retention_days: int
    disposition: str


class GuestBody(ApiModel):
    email: str
    display_name: str
    kind: str = "external"
    auth_method: str = "magic_link_totp"
    expires_at: str = ""
    grants: list[dict[str, object]] = Field(default_factory=list)


class GrantBody(ApiModel):
    portal: str = "records"
    scope: dict[str, object]
    expires_at: str = ""
    watermark: bool = True


class GuestLinkBody(ApiModel):
    email: str
    tenant_slug: str


class GuestSessionBody(ApiModel):
    token: str
    totp: str = ""


class BinderBody(ApiModel):
    title: str
    selection: dict[str, object]
    require_review: bool = False


class IncidentBody(ApiModel):
    agent_id: uuid.UUID | None = None
    agent_version_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    severity: str
    summary: str


class IncidentPatch(ApiModel):
    status: str | None = None
    summary: str | None = None
    severity: str | None = None


class CardPatch(ApiModel):
    known_limitations: str | None = None
    review_due_at: str | None = None
    data_categories: list[str] | None = None


class GovernanceExportBody(ApiModel):
    agent_ids: list[uuid.UUID] = Field(default_factory=list)


class ReplayBody(ApiModel):
    model_id: str = ""


def _step(request: Request) -> None:
    if not stepped_up(request):
        assert_step_up(None, now=utcnow(), ttl_s=1, required=True)


@router.get("/api/v1/evidence", dependencies=[Depends(require_permission("evidence:read"))])
@expose(public=False, permission="evidence:read")
async def list_evidence(
    request: Request,
    source_system: Annotated[str, Query()] = "",
    collection_method: Annotated[str, Query()] = "",
    q: Annotated[str, Query()] = "",
) -> dict[str, object]:
    rows = EvidenceBook(chat(request)).list_items(
        actor(request),
        source_system=source_system,
        collection_method=collection_method,
        query=q,
    )
    return page(rows)


@router.post("/api/v1/evidence", dependencies=[Depends(require_permission("evidence:capture"))])
@expose(public=False, permission="evidence:capture")
async def create_evidence(
    body: EvidenceBody,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> dict[str, object]:
    service = chat(request)
    data = body.text.encode()
    if body.file_id is not None:
        blob = service.blobs.get(body.file_id)
        data = blob if isinstance(blob, bytes) else data
    return EvidenceBook(service).capture(
        actor(request), dump(body), data, idempotency_key=idempotency_key
    )


@router.get("/api/v1/evidence/{evidence_item_id}")
@expose(public=False, permission="evidence:read")
async def get_evidence(evidence_item_id: uuid.UUID, request: Request) -> dict[str, object]:
    return EvidenceBook(chat(request)).get(actor(request), evidence_item_id)


@router.get("/api/v1/evidence/{evidence_item_id}/content")
@expose(public=False, permission="evidence:export")
async def evidence_content(evidence_item_id: uuid.UUID, request: Request) -> Response:
    content_hidden(request)
    who = actor(request)
    row, data = EvidenceBook(chat(request)).content(who, evidence_item_id)
    media = str(row.get("media_type") or "application/octet-stream")
    if who.kind == "guest":
        try:
            data = watermark(data, media, f"{who.display_name} {who.tenant_id}")
        except WatermarkError as exc:
            raise ArError(ErrorCode.WATERMARK_UNSUPPORTED, "watermark_unsupported") from exc
    return Response(content=data, media_type=media)


@router.post("/api/v1/evidence/{evidence_item_id}:verify")
@expose(public=False, permission="evidence:read")
async def verify_evidence(evidence_item_id: uuid.UUID, request: Request) -> dict[str, object]:
    return EvidenceBook(chat(request)).verify(actor(request), evidence_item_id)


@router.get("/api/v1/evidence/{evidence_item_id}/custody")
@expose(public=False, permission="evidence:read")
async def evidence_custody(evidence_item_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(EvidenceBook(chat(request)).custody(actor(request), evidence_item_id))


@router.get("/api/v1/legal-holds", dependencies=[Depends(require_permission("holds:manage"))])
@expose(public=False, permission="holds:manage")
async def list_holds(request: Request) -> dict[str, object]:
    book = HoldBook(chat(request))
    who = actor(request)
    return {"data": book.list_holds(who), "officers": book.officers(who)}


@router.post("/api/v1/legal-holds", dependencies=[Depends(require_permission("holds:manage"))])
@expose(public=False, permission="holds:manage")
async def create_hold(body: HoldBody, request: Request) -> dict[str, object]:
    _step(request)
    return HoldBook(chat(request)).create(actor(request), dump(body))


@router.get(
    "/api/v1/legal-holds/{hold_id}", dependencies=[Depends(require_permission("holds:manage"))]
)
@expose(public=False, permission="holds:manage")
async def get_hold(hold_id: uuid.UUID, request: Request) -> dict[str, object]:
    return HoldBook(chat(request)).get(actor(request), hold_id)


@router.post(
    "/api/v1/legal-holds/{hold_id}:release",
    dependencies=[Depends(require_permission("holds:manage"))],
)
@expose(public=False, permission="holds:manage")
async def release_hold(
    hold_id: uuid.UUID, body: ReleaseBody, request: Request
) -> dict[str, object]:
    _step(request)
    return HoldBook(chat(request)).release(actor(request), hold_id, body.reason)


@router.get("/api/v1/retention-schedules")
@expose(public=False, permission="retention:manage")
async def list_schedules(request: Request) -> dict[str, object]:
    return page(HoldBook(chat(request)).list_schedules(actor(request)))


@router.put(
    "/api/v1/retention-schedules/{record_class}",
    dependencies=[Depends(require_permission("retention:manage"))],
)
@expose(public=False, permission="retention:manage")
async def put_schedule(
    record_class: str, body: ScheduleBody, request: Request
) -> dict[str, object]:
    return HoldBook(chat(request)).put_schedule(actor(request), record_class, dump(body))


@router.get(
    "/api/v1/disposition-certificates",
    dependencies=[Depends(require_permission("audit:read"))],
)
@expose(public=False, permission="audit:read")
async def list_certificates(request: Request) -> dict[str, object]:
    return page(HoldBook(chat(request)).certificates(actor(request)))


@router.get("/api/v1/guests", dependencies=[Depends(require_permission("guests:manage"))])
@expose(public=False, permission="guests:manage")
async def list_guests(request: Request) -> dict[str, object]:
    return page(GuestBook(chat(request)).list_guests(actor(request)))


@router.post("/api/v1/guests", dependencies=[Depends(require_permission("guests:invite"))])
@expose(public=False, permission="guests:invite")
async def invite_guest(body: GuestBody, request: Request) -> dict[str, object]:
    return GuestBook(chat(request)).invite(actor(request), dump(body))


@router.get(
    "/api/v1/guests/{guest_id}", dependencies=[Depends(require_permission("guests:manage"))]
)
@expose(public=False, permission="guests:manage")
async def get_guest(guest_id: uuid.UUID, request: Request) -> dict[str, object]:
    return GuestBook(chat(request)).get(actor(request), guest_id)


@router.post(
    "/api/v1/guests/{guest_id}:revoke",
    dependencies=[Depends(require_permission("guests:manage"))],
)
@expose(public=False, permission="guests:manage")
async def revoke_guest(guest_id: uuid.UUID, request: Request) -> dict[str, object]:
    return GuestBook(chat(request)).revoke(actor(request), guest_id)


@router.post(
    "/api/v1/guests/{guest_id}/grants",
    dependencies=[Depends(require_permission("guests:manage"))],
)
@expose(public=False, permission="guests:manage")
async def create_grant(guest_id: uuid.UUID, body: GrantBody, request: Request) -> dict[str, object]:
    return GuestBook(chat(request)).add_grant(actor(request), guest_id, dump(body))


@router.delete(
    "/api/v1/guests/{guest_id}/grants/{grant_id}",
    dependencies=[Depends(require_permission("guests:manage"))],
)
@expose(public=False, permission="guests:manage")
async def delete_grant(
    guest_id: uuid.UUID, grant_id: uuid.UUID, request: Request
) -> dict[str, bool]:
    GuestBook(chat(request)).revoke_grant(actor(request), guest_id, grant_id)
    return {"deleted": True}


@router.post("/api/v1/auth/guest/request-link")
@expose(public=True, permission=None)
async def request_link(body: GuestLinkBody, request: Request) -> Response:
    GuestBook(chat(request)).request_link(body.email, body.tenant_slug)
    return Response(status_code=202)


@router.post("/api/v1/auth/guest/session")
@expose(public=True, permission=None)
async def guest_session(body: GuestSessionBody, request: Request) -> Response:
    from fastapi.responses import JSONResponse  # noqa: PLC0415

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
        header = request.headers.get("x-guest-session", "")
        session_id = header
    return GuestBook(chat(request)).enroll(session_id)


@router.get("/api/v1/binders")
@expose(public=False, permission="binders:export")
async def list_binders(request: Request) -> dict[str, object]:
    return page(BinderBook(chat(request)).list_binders(actor(request)))


@router.post("/api/v1/binders", dependencies=[Depends(require_permission("binders:export"))])
@expose(public=False, permission="binders:export")
async def create_binder(body: BinderBody, request: Request) -> dict[str, object]:
    return BinderBook(chat(request)).create(actor(request), dump(body))


@router.get("/api/v1/binders/{binder_id}")
@expose(public=False, permission="binders:export")
async def get_binder(binder_id: uuid.UUID, request: Request) -> dict[str, object]:
    return BinderBook(chat(request)).get(actor(request), binder_id)


@router.post(
    "/api/v1/binders/{binder_id}:build",
    status_code=202,
    dependencies=[Depends(require_permission("binders:export"))],
)
@expose(public=False, permission="binders:export")
async def build_binder(binder_id: uuid.UUID, request: Request) -> dict[str, object]:
    return BinderBook(chat(request)).build(actor(request), binder_id)


@router.get("/api/v1/binders/{binder_id}/download")
@expose(public=False, permission="binders:export")
async def download_binder(binder_id: uuid.UUID, request: Request) -> Response:
    data = BinderBook(chat(request)).download(actor(request), binder_id)
    return Response(content=data, media_type="application/zip")


@router.get("/api/v1/agent-cards", dependencies=[Depends(require_permission("ai_governance:read"))])
@expose(public=False, permission="ai_governance:read")
async def list_cards(request: Request) -> dict[str, object]:
    return page(GovernanceBook(chat(request)).list_cards(actor(request)))


@router.patch(
    "/api/v1/agents/{agent_id}/cards/{version}",
    dependencies=[Depends(require_permission("ai_governance:manage"))],
)
@expose(public=False, permission="ai_governance:manage")
async def patch_card(
    agent_id: uuid.UUID, version: int, body: CardPatch, request: Request
) -> dict[str, object]:
    return GovernanceBook(chat(request)).update_card(actor(request), agent_id, version, dump(body))


@router.get(
    "/api/v1/ai-incidents", dependencies=[Depends(require_permission("ai_governance:read"))]
)
@expose(public=False, permission="ai_governance:read")
async def list_incidents(request: Request) -> dict[str, object]:
    return page(GovernanceBook(chat(request)).list_incidents(actor(request)))


@router.post(
    "/api/v1/ai-incidents", dependencies=[Depends(require_permission("ai_governance:manage"))]
)
@expose(public=False, permission="ai_governance:manage")
async def create_incident(body: IncidentBody, request: Request) -> dict[str, object]:
    return GovernanceBook(chat(request)).create_incident(actor(request), dump(body))


@router.patch(
    "/api/v1/ai-incidents/{incident_id}",
    dependencies=[Depends(require_permission("ai_governance:manage"))],
)
@expose(public=False, permission="ai_governance:manage")
async def patch_incident(
    incident_id: uuid.UUID, body: IncidentPatch, request: Request
) -> dict[str, object]:
    return GovernanceBook(chat(request)).update_incident(actor(request), incident_id, dump(body))


@router.get(
    "/api/v1/ai-governance/oversight",
    dependencies=[Depends(require_permission("ai_governance:read"))],
)
@expose(public=False, permission="ai_governance:read")
async def oversight(request: Request) -> dict[str, object]:
    return page(GovernanceBook(chat(request)).oversight(actor(request)))


@router.post(
    "/api/v1/ai-governance:export",
    status_code=202,
    dependencies=[Depends(require_permission("ai_governance:read"))],
)
@expose(public=False, permission="ai_governance:read")
async def export_governance(body: GovernanceExportBody, request: Request) -> dict[str, object]:
    return GovernanceBook(chat(request)).export(actor(request), body.agent_ids)


@router.get("/api/v1/run-records", dependencies=[Depends(require_permission("run_records:read"))])
@expose(public=False, permission="run_records:read")
async def list_run_records(request: Request) -> dict[str, object]:
    return page(RunRecordBook(chat(request)).list_records(actor(request)))


@router.get(
    "/api/v1/run-records/{run_record_id}",
    dependencies=[Depends(require_permission("run_records:read"))],
)
@expose(public=False, permission="run_records:read")
async def get_run_record(run_record_id: uuid.UUID, request: Request) -> dict[str, object]:
    return RunRecordBook(chat(request)).get(actor(request), run_record_id)


@router.post(
    "/api/v1/run-records/{run_record_id}:replay",
    status_code=202,
    dependencies=[Depends(require_permission("run_records:replay"))],
)
@expose(public=False, permission="run_records:replay")
async def replay_run_record(
    run_record_id: uuid.UUID, body: ReplayBody, request: Request
) -> dict[str, object]:
    return RunRecordBook(chat(request)).replay(actor(request), run_record_id, body.model_id)


@router.get(
    "/api/v1/run-records/{run_record_id}/replays/{replay_id}",
    dependencies=[Depends(require_permission("run_records:read"))],
)
@expose(public=False, permission="run_records:read")
async def get_replay(
    run_record_id: uuid.UUID, replay_id: uuid.UUID, request: Request
) -> dict[str, object]:
    return RunRecordBook(chat(request)).get_replay(actor(request), run_record_id, replay_id)


@router.get("/api/v1/tenant/packs")
@expose(public=False, permission=None)
async def tenant_packs(request: Request) -> dict[str, object]:
    from ar_domain.packs.registry import tenant_packs as listed  # noqa: PLC0415

    return page(listed(chat(request), actor(request)))


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
    return HoldBook(chat(request)).erase(actor(request), user_id)


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
