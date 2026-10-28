"""Eval suite catalogue. Spec: docs/03-specs/18-observability-eval.md §4.3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.evals.book import EvalBook, public_row

router = APIRouter()


class SuiteBody(ApiModel):
    name: str
    description: str = ""
    kind: str = "functional"
    agent_id: uuid.UUID | None = None
    gate: dict[str, object] | None = None


class SuitePatch(ApiModel):
    name: str | None = None
    description: str | None = None
    kind: str | None = None
    agent_id: uuid.UUID | None = None
    gate: dict[str, object] | None = None


class CaseBody(ApiModel):
    name: str
    input: dict[str, object]
    assertions: list[dict[str, object]]
    tool_mocks: list[dict[str, object]] | None = None
    tags: list[str] | None = None


class CasePatch(ApiModel):
    name: str | None = None
    input: dict[str, object] | None = None
    assertions: list[dict[str, object]] | None = None
    tool_mocks: list[dict[str, object]] | None = None
    tags: list[str] | None = None


class EvalImportBody(ApiModel):
    file_id: uuid.UUID


class FromConversationBody(ApiModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    assertions: list[dict[str, object]] | None = None
    name: str | None = None
    tags: list[str] | None = None


class EvalRunBody(ApiModel):
    agent_version_ref: str = "published"
    model_alias_override: str | None = None
    baseline_eval_run_id: uuid.UUID | None = None
    tags: list[str] | None = None
    agent_id: uuid.UUID | None = None


def _book(request: Request) -> EvalBook:
    return EvalBook(chat(request))


@router.get("/api/v1/eval-suites", dependencies=[Depends(require_permission("evals:manage"))])
@expose(public=False, permission="evals:manage")
async def list_eval_suites(
    request: Request,
    *,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    rows = _book(request).list_suites(actor(request), agent_id=agent_id, kind=kind)
    return page([public_row(row) for row in rows])


@router.post(
    "/api/v1/eval-suites",
    status_code=201,
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def create_eval_suite(body: SuiteBody, request: Request) -> dict[str, object]:
    return public_row(_book(request).create_suite(actor(request), dump(body)))


@router.get(
    "/api/v1/eval-suites/{suite_id}",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def get_eval_suite(suite_id: uuid.UUID, request: Request) -> dict[str, object]:
    return public_row(_book(request).get_suite(actor(request), suite_id))


@router.patch(
    "/api/v1/eval-suites/{suite_id}",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def update_eval_suite(
    suite_id: uuid.UUID, body: SuitePatch, request: Request
) -> dict[str, object]:
    return public_row(_book(request).update_suite(actor(request), suite_id, dump(body)))


@router.delete(
    "/api/v1/eval-suites/{suite_id}",
    status_code=204,
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def delete_eval_suite(suite_id: uuid.UUID, request: Request) -> None:
    _book(request).delete_suite(actor(request), suite_id)


@router.get(
    "/api/v1/eval-suites/{suite_id}/cases",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def list_eval_cases(suite_id: uuid.UUID, request: Request) -> dict[str, object]:
    rows = _book(request).list_cases(actor(request), suite_id)
    return page([public_row(row) for row in rows])


@router.post(
    "/api/v1/eval-suites/{suite_id}/cases",
    status_code=201,
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def create_eval_case(
    suite_id: uuid.UUID, body: CaseBody, request: Request
) -> dict[str, object]:
    return public_row(_book(request).create_case(actor(request), suite_id, dump(body)))


@router.patch(
    "/api/v1/eval-suites/{suite_id}/cases/{case_id}",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def update_eval_case(
    suite_id: uuid.UUID, case_id: uuid.UUID, body: CasePatch, request: Request
) -> dict[str, object]:
    return public_row(_book(request).update_case(actor(request), suite_id, case_id, dump(body)))


@router.delete(
    "/api/v1/eval-suites/{suite_id}/cases/{case_id}",
    status_code=204,
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def delete_eval_case(suite_id: uuid.UUID, case_id: uuid.UUID, request: Request) -> None:
    _book(request).delete_case(actor(request), suite_id, case_id)


@router.post(
    "/api/v1/eval-suites/{suite_id}/cases:import",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def import_eval_cases(
    suite_id: uuid.UUID, body: EvalImportBody, request: Request
) -> dict[str, object]:
    return _book(request).import_cases(actor(request), suite_id, body.file_id)


@router.post(
    "/api/v1/eval-suites/{suite_id}/cases:from-conversation",
    status_code=201,
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def case_from_conversation(
    suite_id: uuid.UUID, body: FromConversationBody, request: Request
) -> dict[str, object]:
    return public_row(_book(request).case_from_conversation(actor(request), suite_id, dump(body)))


@router.post(
    "/api/v1/eval-suites/{suite_id}:run",
    status_code=202,
    dependencies=[Depends(require_permission("evals:run"))],
)
@expose(public=False, permission="evals:run")
async def run_eval_suite(suite_id: uuid.UUID, body: EvalRunBody, request: Request) -> JSONResponse:
    row = _book(request).start_run(actor(request), suite_id, dump(body))
    return JSONResponse(public_row(row), status_code=202)
