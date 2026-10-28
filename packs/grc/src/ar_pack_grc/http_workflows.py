"""Workflow routes mounted under `/api/v1/ext/grc`."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request

from ar_api.deps import expose
from ar_api.routers.tooling import actor, chat
from ar_common.errors import NotFoundError
from ar_pack_grc import (
    campaigns,
    ethics,
    exceptions,
    incidents,
    policies,
    questionnaires,
    regulatory,
    risks,
    vendors,
)
from ar_pack_grc.access import pack_enabled, snake_body

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

router = APIRouter()


def _caller(request: Request, *permissions: str) -> Actor:
    from ar_pack_grc.access import require_enabled  # noqa: PLC0415

    who = actor(request)
    require_enabled(chat(request), who, *permissions)
    return who


def _query(request: Request) -> dict[str, Any]:
    return snake_body(dict(request.query_params.items()))


def _guest_or(request: Request, *permissions: str) -> Actor:
    who = actor(request)
    if not pack_enabled(chat(request), who.tenant_id):
        raise NotFoundError()
    if who.kind == "guest":
        return who
    return _caller(request, *permissions)


@router.get("/assets")
@expose(public=False, permission="grc.risks:read")
async def list_assets(request: Request) -> dict[str, Any]:
    return risks.list_assets(chat(request), _caller(request, "grc.risks:read"))


@router.post("/assets")
@expose(public=False, permission="grc.risks:manage")
async def create_asset(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return risks.create_asset(chat(request), _caller(request, "grc.risks:manage"), body)


@router.get("/risks")
@expose(public=False, permission="grc.risks:read")
async def list_risks(request: Request) -> dict[str, Any]:
    return risks.list_risks(chat(request), _caller(request, "grc.risks:read"), _query(request))


@router.post("/risks")
@expose(public=False, permission="grc.risks:manage")
async def create_risk(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return risks.create_risk(chat(request), _caller(request, "grc.risks:manage"), body)


@router.get("/risks/{risk_id}")
@expose(public=False, permission="grc.risks:read")
async def get_risk(risk_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return risks.get_risk(chat(request), _caller(request, "grc.risks:read"), risk_id)


@router.patch("/risks/{risk_id}")
@expose(public=False, permission="grc.risks:manage")
async def patch_risk(risk_id: uuid.UUID, request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return risks.patch_risk(chat(request), _caller(request, "grc.risks:manage"), risk_id, body)


@router.post("/risks/{risk_id}:accept")
@expose(public=False, permission="grc.risks:manage")
async def accept_risk(risk_id: uuid.UUID, request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return risks.accept_risk(chat(request), _caller(request, "grc.risks:manage"), risk_id, body)


@router.get("/risks/{risk_id}/treatments")
@expose(public=False, permission="grc.risks:read")
async def list_treatments(risk_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return risks.list_treatments(chat(request), _caller(request, "grc.risks:read"), risk_id)


@router.post("/risks/{risk_id}/treatments")
@expose(public=False, permission="grc.risks:manage")
async def add_treatment(
    risk_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return risks.add_treatment(chat(request), _caller(request, "grc.risks:manage"), risk_id, body)


@router.get("/vendors")
@expose(public=False, permission="grc.vendors:read")
async def list_vendors(request: Request) -> dict[str, Any]:
    return vendors.list_vendors(
        chat(request), _caller(request, "grc.vendors:read"), _query(request)
    )


@router.post("/vendors")
@expose(public=False, permission="grc.vendors:manage")
async def create_vendor(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return vendors.create_vendor(chat(request), _caller(request, "grc.vendors:manage"), body)


@router.get("/vendors/{vendor_id}")
@expose(public=False, permission="grc.vendors:read")
async def get_vendor(vendor_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return vendors.get_vendor(chat(request), _caller(request, "grc.vendors:read"), vendor_id)


@router.patch("/vendors/{vendor_id}")
@expose(public=False, permission="grc.vendors:manage")
async def patch_vendor(
    vendor_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return vendors.patch_vendor(
        chat(request), _caller(request, "grc.vendors:manage"), vendor_id, body
    )


@router.get("/vendors/{vendor_id}/assessments")
@expose(public=False, permission="grc.vendors:read")
async def list_assessments(vendor_id: uuid.UUID, request: Request) -> dict[str, Any]:
    who = _guest_or(request, "grc.vendors:read")
    return vendors.list_assessments(chat(request), who, vendor_id)


@router.post("/vendors/{vendor_id}/assessments")
@expose(public=False, permission="grc.vendors:manage")
async def create_assessment(
    vendor_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return vendors.create_assessment(
        chat(request), _caller(request, "grc.vendors:manage"), vendor_id, body
    )


@router.post("/vendor-assessments/{assessment_id}:score")
@expose(public=False, permission="grc.vendors:manage")
async def score_assessment(
    assessment_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return vendors.score_assessment(
        chat(request), _caller(request, "grc.vendors:manage"), assessment_id, body
    )


@router.get("/policies")
@expose(public=False, permission="grc.policies:read")
async def list_policies(request: Request) -> dict[str, Any]:
    return policies.list_policies(
        chat(request), _caller(request, "grc.policies:read"), _query(request)
    )


@router.post("/policies")
@expose(public=False, permission="grc.policies:manage")
async def create_policy(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return policies.create_policy(chat(request), _caller(request, "grc.policies:manage"), body)


@router.get("/policies/{policy_id}")
@expose(public=False, permission="grc.policies:read")
async def get_policy(policy_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return policies.get_policy(chat(request), _caller(request, "grc.policies:read"), policy_id)


@router.post("/policies/{policy_id}/versions")
@expose(public=False, permission="grc.policies:manage")
async def add_version(
    policy_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return policies.add_version(
        chat(request), _caller(request, "grc.policies:manage"), policy_id, body
    )


@router.post("/policies/{policy_id}:submit-review")
@expose(public=False, permission="grc.policies:manage")
async def submit_policy(policy_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return policies.submit_review(chat(request), _caller(request, "grc.policies:manage"), policy_id)


@router.post("/policy-versions/{version_id}:publish")
@expose(public=False, permission="grc.policies:manage")
async def publish_policy(version_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return policies.publish(chat(request), _caller(request, "grc.policies:manage"), version_id)


@router.get("/obligations")
@expose(public=False, permission="grc.obligations:read")
async def list_obligations(request: Request) -> dict[str, Any]:
    return regulatory.list_obligations(
        chat(request), _caller(request, "grc.obligations:read"), _query(request)
    )


@router.post("/obligations")
@expose(public=False, permission="grc.obligations:manage")
async def create_obligation(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return regulatory.create_obligation(
        chat(request), _caller(request, "grc.obligations:manage"), body
    )


@router.patch("/obligations/{obligation_id}")
@expose(public=False, permission="grc.obligations:manage")
async def patch_obligation(
    obligation_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return regulatory.patch_obligation(
        chat(request), _caller(request, "grc.obligations:manage"), obligation_id, body
    )


@router.get("/regulatory-changes")
@expose(public=False, permission="grc.obligations:read")
async def list_changes(request: Request) -> dict[str, Any]:
    return regulatory.list_changes(
        chat(request), _caller(request, "grc.obligations:read"), _query(request)
    )


@router.post("/regulatory-changes/{change_id}:triage")
@expose(public=False, permission="grc.obligations:manage")
async def triage_change(
    change_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return regulatory.triage(
        chat(request), _caller(request, "grc.obligations:manage"), change_id, body
    )


@router.get("/regulator-feeds")
@expose(public=False, permission="grc.obligations:read")
async def list_feeds(request: Request) -> dict[str, Any]:
    return regulatory.list_feeds(chat(request), _caller(request, "grc.obligations:read"))


@router.post("/regulator-feeds")
@expose(public=False, permission="grc.obligations:manage")
async def create_feed(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return regulatory.create_feed(chat(request), _caller(request, "grc.obligations:manage"), body)


@router.get("/incidents")
@expose(public=False, permission="grc.incidents:read")
async def list_incidents(request: Request) -> dict[str, Any]:
    return incidents.list_incidents(
        chat(request), _caller(request, "grc.incidents:read"), _query(request)
    )


@router.post("/incidents")
@expose(public=False, permission="grc.incidents:manage")
async def create_incident(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return incidents.create_incident(chat(request), _caller(request, "grc.incidents:manage"), body)


@router.get("/incidents/{incident_id}")
@expose(public=False, permission="grc.incidents:read")
async def get_incident(incident_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return incidents.get_incident(
        chat(request), _caller(request, "grc.incidents:read"), incident_id
    )


@router.patch("/incidents/{incident_id}")
@expose(public=False, permission="grc.incidents:manage")
async def patch_incident(
    incident_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return incidents.patch_incident(
        chat(request), _caller(request, "grc.incidents:manage"), incident_id, body
    )


@router.post("/incidents/{incident_id}:start-clock")
@expose(public=False, permission="grc.incidents:manage")
async def start_clock(
    incident_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return incidents.start_clock(
        chat(request), _caller(request, "grc.incidents:manage"), incident_id, body
    )


@router.post("/incidents/{incident_id}:file-notification")
@expose(public=False, permission="grc.incidents:manage")
async def file_notification(
    incident_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return incidents.file_notification(
        chat(request), _caller(request, "grc.incidents:manage"), incident_id, body
    )


@router.get("/campaigns")
@expose(public=False, permission="grc.campaigns:read")
async def list_campaigns(request: Request) -> dict[str, Any]:
    return campaigns.list_campaigns(
        chat(request), _caller(request, "grc.campaigns:read"), _query(request)
    )


@router.post("/campaigns")
@expose(public=False, permission="grc.campaigns:manage")
async def create_campaign(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return campaigns.create_campaign(chat(request), _caller(request, "grc.campaigns:manage"), body)


@router.get("/campaigns/{campaign_id}")
@expose(public=False, permission="grc.campaigns:read")
async def get_campaign(campaign_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return campaigns.get_campaign(
        chat(request), _caller(request, "grc.campaigns:read"), campaign_id
    )


@router.get("/answer-library")
@expose(public=False, permission="grc.questionnaires:read")
async def list_answers(request: Request) -> dict[str, Any]:
    return questionnaires.list_answers(
        chat(request), _caller(request, "grc.questionnaires:read"), _query(request)
    )


@router.post("/answer-library")
@expose(public=False, permission="grc.questionnaires:manage")
async def create_answer(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return questionnaires.create_answer(
        chat(request), _caller(request, "grc.questionnaires:manage"), body
    )


@router.patch("/answer-library/{answer_id}")
@expose(public=False, permission="grc.questionnaires:manage")
async def patch_answer(
    answer_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return questionnaires.patch_answer(
        chat(request), _caller(request, "grc.questionnaires:manage"), answer_id, body
    )


@router.post("/questionnaires:draft", status_code=202)
@expose(public=False, permission="grc.questionnaires:manage")
async def draft_questionnaire(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return questionnaires.draft_job(
        chat(request), _caller(request, "grc.questionnaires:manage"), body
    )


@router.post("/questionnaires/{job_id}:export")
@expose(public=False, permission="grc.questionnaires:manage")
async def export_questionnaire(job_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return questionnaires.export_job(
        chat(request), _caller(request, "grc.questionnaires:manage"), job_id
    )


@router.get("/exceptions")
@expose(public=False, permission="grc.controls:read")
async def list_exceptions(request: Request) -> dict[str, Any]:
    return exceptions.list_exceptions(
        chat(request), _caller(request, "grc.controls:read"), _query(request)
    )


@router.post("/exceptions")
@expose(public=False, permission="grc.exceptions:manage")
async def create_exception(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return exceptions.create_exception(
        chat(request), _caller(request, "grc.exceptions:manage"), body
    )


@router.get("/ethics-cases")
@expose(public=False, permission="grc.ethics:manage")
async def list_ethics(request: Request) -> dict[str, Any]:
    who = actor(request)
    if not pack_enabled(chat(request), who.tenant_id):
        raise NotFoundError()
    return ethics.list_cases(chat(request), who)


@router.get("/ethics-cases/{case_id}")
@expose(public=False, permission="grc.ethics:manage")
async def get_ethics(case_id: uuid.UUID, request: Request) -> dict[str, Any]:
    who = actor(request)
    if not pack_enabled(chat(request), who.tenant_id):
        raise NotFoundError()
    return ethics.get_case(chat(request), who, case_id)


@router.post("/ethics-cases")
@expose(public=False, permission="grc.ethics:manage")
async def open_ethics(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return ethics.open_case(chat(request), _caller(request, "grc.ethics:manage"), body)
