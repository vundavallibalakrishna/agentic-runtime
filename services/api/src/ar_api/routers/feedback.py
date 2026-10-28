"""Feedback inbox for builders. Spec: docs/03-specs/18-observability-eval.md §4.3."""

from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_domain.evals.book import EvalBook, public_row

router = APIRouter()


@router.get("/api/v1/feedback", dependencies=[Depends(require_permission("evals:manage"))])
@expose(public=False, permission="evals:manage")
async def list_feedback(request: Request) -> dict[str, object]:
    rows = EvalBook(chat(request)).list_feedback(actor(request))
    return page([public_row(row) for row in rows])
