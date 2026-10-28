"""HTTP mount `/api/v1/ext/grc`. Disabled tenants receive 404."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request, Response

from ar_api.deps import expose
from ar_api.routers.tooling import actor, chat
from ar_pack_grc import ccm, entities, evidence_links, findings, frameworks, mappings
from ar_pack_grc import tests as control_tests
from ar_pack_grc.access import require_enabled, snake_body
from ar_pack_grc.http_workflows import router as workflow_router

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

router = APIRouter(prefix="/api/v1/ext/grc", tags=["grc"])


def _caller(request: Request, *permissions: str) -> Actor:
    who = actor(request)
    require_enabled(chat(request), who, *permissions)
    return who


def _query(request: Request) -> dict[str, Any]:
    return snake_body(dict(request.query_params.items()))


@router.get("/frameworks")
@expose(public=False, permission="grc.frameworks:read")
async def list_frameworks(request: Request) -> dict[str, Any]:
    return frameworks.list_frameworks(
        chat(request), _caller(request, "grc.frameworks:read"), _query(request)
    )


@router.post("/frameworks")
@expose(public=False, permission="grc.frameworks:manage")
async def create_framework(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return frameworks.create_framework(
        chat(request), _caller(request, "grc.frameworks:manage"), body
    )


@router.get("/frameworks/{framework_id}:export-oscal")
@expose(public=False, permission="grc.frameworks:read")
async def export_oscal(framework_id: uuid.UUID, request: Request) -> dict[str, Any]:
    include = str(_query(request).get("include_mappings") or "").lower() == "true"
    return frameworks.export_oscal(
        chat(request),
        _caller(request, "grc.frameworks:read"),
        framework_id,
        include_mappings=include,
    )


@router.post("/frameworks/{framework_id}:import-licensed-text")
@expose(public=False, permission="grc.frameworks:manage")
async def import_licensed_text(
    framework_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    payload = snake_body(body)
    return frameworks.import_statements(
        chat(request),
        _caller(request, "grc.frameworks:manage"),
        framework_id,
        uuid.UUID(str(payload["file_id"])),
        attestation=payload.get("attestation") is True,
    )


@router.get("/frameworks/{framework_id}")
@expose(public=False, permission="grc.frameworks:read")
async def get_framework(framework_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return frameworks.get_framework(
        chat(request), _caller(request, "grc.frameworks:read"), framework_id
    )


@router.patch("/frameworks/{framework_id}")
@expose(public=False, permission="grc.frameworks:manage")
async def patch_framework(
    framework_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return frameworks.patch_framework(
        chat(request), _caller(request, "grc.frameworks:manage"), framework_id, body
    )


@router.post("/frameworks:import-oscal")
@expose(public=False, permission="grc.frameworks:manage")
async def import_oscal(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    payload = snake_body(body)
    return frameworks.import_oscal(
        chat(request), _caller(request, "grc.frameworks:manage"), uuid.UUID(str(payload["file_id"]))
    )


@router.get("/frameworks/{framework_id}/requirements")
@expose(public=False, permission="grc.frameworks:read")
async def list_requirements(framework_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return frameworks.list_requirements(
        chat(request), _caller(request, "grc.frameworks:read"), framework_id
    )


@router.get("/requirements/{requirement_id}")
@expose(public=False, permission="grc.frameworks:read")
async def get_requirement(requirement_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return frameworks.get_requirement(
        chat(request), _caller(request, "grc.frameworks:read"), requirement_id
    )


@router.get("/controls")
@expose(public=False, permission="grc.controls:read")
async def list_controls(request: Request) -> dict[str, Any]:
    return frameworks.list_controls(
        chat(request), _caller(request, "grc.controls:read"), _query(request)
    )


@router.post("/controls")
@expose(public=False, permission="grc.controls:manage")
async def create_control(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return frameworks.create_control(chat(request), _caller(request, "grc.controls:manage"), body)


@router.get("/controls/{control_id}")
@expose(public=False, permission="grc.controls:read")
async def get_control(control_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return frameworks.get_control(chat(request), _caller(request, "grc.controls:read"), control_id)


@router.patch("/controls/{control_id}")
@expose(public=False, permission="grc.controls:manage")
async def patch_control(
    control_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return frameworks.patch_control(
        chat(request), _caller(request, "grc.controls:manage"), control_id, body
    )


@router.get("/control-mappings")
@expose(public=False, permission="grc.controls:read")
async def list_mappings(request: Request) -> dict[str, Any]:
    return mappings.list_mappings(
        chat(request), _caller(request, "grc.controls:read"), _query(request)
    )


@router.post("/control-mappings")
@expose(public=False, permission="grc.controls:manage")
async def create_mapping(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return mappings.create_mapping(chat(request), _caller(request, "grc.controls:manage"), body)


@router.post("/control-mappings/{mapping_id}:confirm")
@expose(public=False, permission="grc.controls:manage")
async def confirm_mapping(mapping_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return mappings.confirm_mapping(
        chat(request), _caller(request, "grc.controls:manage"), mapping_id
    )


@router.post("/control-mappings/{mapping_id}:reject")
@expose(public=False, permission="grc.controls:manage")
async def reject_mapping(mapping_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return mappings.reject_mapping(
        chat(request), _caller(request, "grc.controls:manage"), mapping_id
    )


@router.post("/control-mappings:suggest", status_code=202)
@expose(public=False, permission="grc.controls:read")
async def suggest_mappings(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return mappings.suggest(chat(request), _caller(request, "grc.controls:read"), body, agent=False)


@router.get("/evidence-links")
@expose(public=False, permission="grc.controls:read")
async def list_evidence_links(request: Request) -> dict[str, Any]:
    return evidence_links.list_links(
        chat(request), _caller(request, "grc.controls:read"), _query(request)
    )


@router.post("/evidence-links")
@expose(public=False, permission="grc.evidence:link")
async def create_evidence_link(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    who = _caller(request, "grc.evidence:link", "evidence:read")
    return evidence_links.create_link(chat(request), who, body)


@router.delete("/evidence-links/{link_id}", status_code=204)
@expose(public=False, permission="grc.evidence:link")
async def delete_evidence_link(link_id: uuid.UUID, request: Request) -> Response:
    evidence_links.delete_link(chat(request), _caller(request, "grc.evidence:link"), link_id)
    return Response(status_code=204)


@router.get("/control-tests")
@expose(public=False, permission="grc.tests:read")
async def list_control_tests(request: Request) -> dict[str, Any]:
    return control_tests.list_tests(
        chat(request), _caller(request, "grc.tests:read"), _query(request)
    )


@router.post("/control-tests")
@expose(public=False, permission="grc.controls:manage")
async def create_control_test(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return control_tests.create_test(chat(request), _caller(request, "grc.controls:manage"), body)


@router.patch("/control-tests/{test_id}")
@expose(public=False, permission="grc.controls:manage")
async def patch_control_test(
    test_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return control_tests.patch_test(
        chat(request), _caller(request, "grc.controls:manage"), test_id, body
    )


@router.post("/control-tests/{test_id}:run", status_code=202)
@expose(public=False, permission="grc.tests:run")
async def run_control_test(test_id: uuid.UUID, request: Request) -> dict[str, Any]:
    who = _caller(
        request,
        "grc.tests:run",
        "grc.evidence:link",
        "evidence:read",
        "grc.findings:manage",
    )
    return ccm.run_test(chat(request), who, test_id)


@router.get("/test-results")
@expose(public=False, permission="grc.tests:read")
async def list_test_results(request: Request) -> dict[str, Any]:
    return control_tests.list_results(
        chat(request), _caller(request, "grc.tests:read"), _query(request)
    )


@router.get("/findings")
@expose(public=False, permission="grc.findings:read")
async def list_findings(request: Request) -> dict[str, Any]:
    return findings.list_findings(
        chat(request), _caller(request, "grc.findings:read"), _query(request)
    )


@router.post("/findings")
@expose(public=False, permission="grc.findings:manage")
async def create_finding(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return findings.create_finding(chat(request), _caller(request, "grc.findings:manage"), body)


@router.get("/findings/{finding_id}")
@expose(public=False, permission="grc.findings:read")
async def get_finding(finding_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return findings.get_finding(chat(request), _caller(request, "grc.findings:read"), finding_id)


@router.patch("/findings/{finding_id}")
@expose(public=False, permission="grc.findings:manage")
async def patch_finding(
    finding_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return findings.patch_finding(
        chat(request), _caller(request, "grc.findings:manage"), finding_id, body
    )


@router.post("/findings/{finding_id}:close")
@expose(public=False, permission="grc.findings:manage")
async def close_finding(
    finding_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    who = _caller(request, "grc.findings:manage", "evidence:read")
    return findings.close_finding(chat(request), who, finding_id, body)


@router.get("/issues")
@expose(public=False, permission="grc.findings:read")
async def list_issues(request: Request) -> dict[str, Any]:
    return findings.list_issues(
        chat(request), _caller(request, "grc.findings:read"), _query(request)
    )


@router.post("/issues")
@expose(public=False, permission="grc.findings:manage")
async def create_issue(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return findings.create_issue(chat(request), _caller(request, "grc.findings:manage"), body)


@router.patch("/issues/{issue_id}")
@expose(public=False, permission="grc.findings:manage")
async def patch_issue(
    issue_id: uuid.UUID, request: Request, body: dict[str, Any]
) -> dict[str, Any]:
    return findings.patch_issue(
        chat(request), _caller(request, "grc.findings:manage"), issue_id, body
    )


@router.get("/entities")
@expose(public=False, permission="grc.entities:read")
async def list_entities(request: Request) -> dict[str, Any]:
    return entities.list_entities(chat(request), _caller(request, "grc.entities:read"))


@router.post("/entities")
@expose(public=False, permission="grc.entities:manage")
async def create_entity(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    return entities.create_entity(chat(request), _caller(request, "grc.entities:manage"), body)


@router.get("/entities/{entity_id}/posture")
@expose(public=False, permission="grc.entities:read")
async def entity_posture(entity_id: uuid.UUID, request: Request) -> dict[str, Any]:
    return entities.posture(chat(request), _caller(request, "grc.entities:read"), entity_id)


router.include_router(workflow_router)
