"""Review queues and sign-off. Spec: docs/03-specs/09-policy-approvals.md §11."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page, stepped_up
from ar_contracts.api_model import ApiModel
from ar_domain.approvals.reviews import ReviewBook

router = APIRouter()


class QueueBody(ApiModel):
    slug: str = ""
    name: str = ""
    subject_type: str = ""
    levels: list[dict[str, object]] = Field(default_factory=list)
    statement_template: str = ""


class QueuePatch(ApiModel):
    name: str | None = None
    levels: list[dict[str, object]] | None = None
    statement_template: str | None = None


class ItemBody(ApiModel):
    queue_id: uuid.UUID
    subject_type: str = ""
    subject_id: uuid.UUID
    subject_ref: dict[str, object] = Field(default_factory=dict)
    content_hash: str
    statement_text: str


class ReviewDecideBody(ApiModel):
    decision: str
    comment: str = ""
    content_hash: str
    statement_hash: str
    delegated_to_user_id: uuid.UUID | None = None


class BulkItem(ApiModel):
    review_item_id: uuid.UUID
    content_hash: str
    statement_hash: str


class BulkBody(ApiModel):
    decision: str
    comment: str = ""
    items: list[BulkItem]


@router.get("/api/v1/review-queues", dependencies=[Depends(require_permission("reviews:read"))])
@expose(public=False, permission="reviews:read")
async def list_queues(request: Request) -> dict[str, object]:
    return page(ReviewBook(chat(request)).list_queues(actor(request)))


@router.post("/api/v1/review-queues", dependencies=[Depends(require_permission("reviews:manage"))])
@expose(public=False, permission="reviews:manage")
async def create_queue(body: QueueBody, request: Request) -> dict[str, object]:
    return ReviewBook(chat(request)).create_queue(actor(request), dump(body))


@router.get(
    "/api/v1/review-queues/{queue_id}",
    dependencies=[Depends(require_permission("reviews:read"))],
)
@expose(public=False, permission="reviews:read")
async def get_queue(queue_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ReviewBook(chat(request)).get_queue(actor(request), queue_id)


@router.patch(
    "/api/v1/review-queues/{queue_id}",
    dependencies=[Depends(require_permission("reviews:manage"))],
)
@expose(public=False, permission="reviews:manage")
async def patch_queue(queue_id: uuid.UUID, body: QueuePatch, request: Request) -> dict[str, object]:
    return ReviewBook(chat(request)).patch_queue(actor(request), queue_id, dump(body))


@router.delete(
    "/api/v1/review-queues/{queue_id}",
    dependencies=[Depends(require_permission("reviews:manage"))],
)
@expose(public=False, permission="reviews:manage")
async def delete_queue(queue_id: uuid.UUID, request: Request) -> dict[str, bool]:
    ReviewBook(chat(request)).delete_queue(actor(request), queue_id)
    return {"deleted": True}


@router.get("/api/v1/review-items", dependencies=[Depends(require_permission("reviews:read"))])
@expose(public=False, permission="reviews:read")
async def list_items(
    request: Request,
    scope: Annotated[str, Query()] = "to_decide",
    status: Annotated[str | None, Query()] = None,
    queue_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    return page(
        ReviewBook(chat(request)).list_items(
            actor(request), scope=scope, status=status, queue_id=queue_id
        )
    )


@router.post("/api/v1/review-items", dependencies=[Depends(require_permission("reviews:read"))])
@expose(public=False, permission="reviews:read")
async def open_item(body: ItemBody, request: Request) -> dict[str, object]:
    return ReviewBook(chat(request)).open_item(actor(request), dump(body))


@router.get(
    "/api/v1/review-items/{review_item_id}",
    dependencies=[Depends(require_permission("reviews:read"))],
)
@expose(public=False, permission="reviews:read")
async def get_item(review_item_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ReviewBook(chat(request)).get_item(actor(request), review_item_id)


@router.post(
    "/api/v1/review-items/{review_item_id}:decide",
    dependencies=[Depends(require_permission("reviews:decide"))],
)
@expose(public=False, permission="reviews:decide")
async def decide_item(
    review_item_id: uuid.UUID, body: ReviewDecideBody, request: Request
) -> dict[str, object]:
    return ReviewBook(chat(request)).decide(
        actor(request), review_item_id, dump(body), stepped_up=stepped_up(request)
    )


@router.post(
    "/api/v1/review-items:bulk-decide",
    dependencies=[Depends(require_permission("reviews:decide"))],
)
@expose(public=False, permission="reviews:decide")
async def bulk_decide(body: BulkBody, request: Request) -> dict[str, object]:
    return ReviewBook(chat(request)).bulk(
        actor(request), dump(body), stepped_up=stepped_up(request)
    )
