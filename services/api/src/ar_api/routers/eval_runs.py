"""Eval run reads. Spec: docs/03-specs/18-observability-eval.md §4.3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_domain.evals.book import EvalBook, public_row

router = APIRouter()


def _book(request: Request) -> EvalBook:
    return EvalBook(chat(request))


@router.get("/api/v1/eval-runs", dependencies=[Depends(require_permission("evals:manage"))])
@expose(public=False, permission="evals:manage")
async def list_eval_runs(
    request: Request,
    *,
    suite_id: Annotated[uuid.UUID | None, Query()] = None,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    rows = _book(request).list_runs(
        actor(request), suite_id=suite_id, agent_id=agent_id, status=status
    )
    return page([public_row(row) for row in rows])


@router.get(
    "/api/v1/eval-runs/{eval_run_id}",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def get_eval_run(eval_run_id: uuid.UUID, request: Request) -> dict[str, object]:
    return public_row(_book(request).get_run(actor(request), eval_run_id))


@router.get(
    "/api/v1/eval-runs/{eval_run_id}/results",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def list_eval_results(eval_run_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page([public_row(row) for row in _book(request).results(actor(request), eval_run_id)])


@router.post(
    "/api/v1/eval-runs/{eval_run_id}:cancel",
    dependencies=[Depends(require_permission("evals:manage"))],
)
@expose(public=False, permission="evals:manage")
async def cancel_eval_run(eval_run_id: uuid.UUID, request: Request) -> dict[str, object]:
    return public_row(_book(request).cancel(actor(request), eval_run_id))
