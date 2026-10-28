"""Routines API. Spec: docs/03-specs/15-routines-triggers.md §5."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_common.errors import ConflictError
from ar_contracts.api_model import ApiModel
from ar_domain.durable.hydrate import reload_routines
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.dispatch import client_for, start_run, sync_schedule

router = APIRouter()


class TriggerBody(ApiModel):
    type: str
    cron: str | None = None
    timezone: str | None = None
    jitter_s: int = 0
    catchup_window_s: int = 0
    config: dict[str, str] = Field(default_factory=dict)


class DeliveryBody(ApiModel):
    type: str
    integration: str | None = None
    channel: str | None = None
    pre_approved: bool = False
    config: dict[str, str] = Field(default_factory=dict)


class RoutineBody(ApiModel):
    name: str
    description: str = ""
    agent_id: uuid.UUID
    agent_version_id: uuid.UUID | None = None
    instructions: str
    trigger: TriggerBody
    event_filter: str | None = None
    delivery: list[DeliveryBody] = Field(default_factory=list)
    budget: dict[str, int] | None = None
    max_runs_per_day: int | None = None
    concurrency_policy: str | None = None
    run_as: str | None = None
    service_account_id: uuid.UUID | None = None


class RoutinePatch(ApiModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    agent_id: uuid.UUID | None = None
    trigger: TriggerBody | None = None
    delivery: list[DeliveryBody] | None = None


class RoutineRunBody(ApiModel):
    input: str | None = None
    test: bool = False


class TransferBody(ApiModel):
    new_owner_user_id: uuid.UUID


class PreviewBody(ApiModel):
    cron: str
    timezone: str


class ChannelEventBody(ApiModel):
    event: str = "channel_event"
    integration_id: str = ""
    external_event_id: str = ""
    message_id: str = ""


def _book(request: Request) -> RoutineBook:
    return RoutineBook(chat(request))


@router.get("/api/v1/routines", dependencies=[Depends(require_permission("routines:create"))])
@expose(public=False, permission="routines:create")
async def list_routines(  # noqa: PLR0917
    request: Request,
    q: Annotated[str, Query()] = "",
    status: Annotated[str, Query()] = "",
    owner: Annotated[str, Query()] = "",
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    trigger_type: Annotated[str, Query()] = "",
) -> dict[str, object]:
    await reload_routines(chat(request))
    rows = _book(request).list_routines(
        actor(request),
        query=q,
        status=status,
        owner=owner,
        agent_id=agent_id,
        trigger_type=trigger_type,
    )
    return page(rows)


@router.post(
    "/api/v1/routines",
    status_code=201,
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def create_routine(body: RoutineBody, request: Request) -> dict[str, object]:
    result = _book(request).create(actor(request), dump(body))
    await sync_schedule(chat(request), uuid.UUID(str(result["id"])))
    return result


@router.post(
    "/api/v1/routines:preview-schedule",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def preview_schedule(body: PreviewBody, request: Request) -> dict[str, object]:
    return _book(request).preview(dump(body))


@router.get(
    "/api/v1/routines/{routine_id}",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def get_routine(routine_id: uuid.UUID, request: Request) -> dict[str, object]:
    await reload_routines(chat(request))
    return _book(request).detail(actor(request), routine_id)


@router.patch(
    "/api/v1/routines/{routine_id}",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def patch_routine(
    routine_id: uuid.UUID, body: RoutinePatch, request: Request
) -> dict[str, object]:
    result = _book(request).patch(actor(request), routine_id, dump(body))
    await sync_schedule(chat(request), routine_id)
    return result


@router.delete(
    "/api/v1/routines/{routine_id}",
    status_code=204,
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def delete_routine(routine_id: uuid.UUID, request: Request) -> None:
    await sync_schedule(chat(request), routine_id, deleted=True)
    _book(request).delete(actor(request), routine_id)


@router.post(
    "/api/v1/routines/{routine_id}:run",
    status_code=202,
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def run_routine(
    routine_id: uuid.UUID, body: RoutineRunBody, request: Request
) -> dict[str, object]:
    store = chat(request)
    durable = store.durable_engine is not None
    if durable:
        client_for(store)
    result = _book(request).run_now(actor(request), routine_id, dump(body), execute=not durable)
    if durable:
        await start_run(store, uuid.UUID(str(result["run_id"])))
    return result


@router.post(
    "/api/v1/routines/{routine_id}:pause",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def pause_routine(routine_id: uuid.UUID, request: Request) -> dict[str, object]:
    result = _book(request).pause(actor(request), routine_id)
    await sync_schedule(chat(request), routine_id)
    return result


@router.post(
    "/api/v1/routines/{routine_id}:resume",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def resume_routine(routine_id: uuid.UUID, request: Request) -> dict[str, object]:
    result = _book(request).resume(actor(request), routine_id)
    await sync_schedule(chat(request), routine_id)
    return result


@router.post(
    "/api/v1/routines/{routine_id}:transfer",
    dependencies=[Depends(require_permission("routines:manage_all"))],
)
@expose(public=False, permission="routines:manage_all")
async def transfer_routine(
    routine_id: uuid.UUID, body: TransferBody, request: Request
) -> dict[str, object]:
    return _book(request).transfer(actor(request), routine_id, body.new_owner_user_id)


@router.post(
    "/api/v1/routines/{routine_id}:rotate-webhook-secret",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def rotate_secret(routine_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).rotate(actor(request), routine_id)


@router.get(
    "/api/v1/routines/{routine_id}/events",
    dependencies=[Depends(require_permission("routines:create"))],
)
@expose(public=False, permission="routines:create")
async def list_events(routine_id: uuid.UUID, request: Request) -> dict[str, object]:
    await reload_routines(chat(request))
    return page(_book(request).events(actor(request), routine_id))


@router.post("/api/v1/hooks/routines/{token}")
@expose(public=True, permission=None)
async def routine_webhook(token: str, request: Request) -> JSONResponse:
    raw = await request.body()
    header = request.headers.get("x-ar-signature", "")
    idem = request.headers.get("x-idempotency-key", "")
    store = chat(request)
    durable = store.durable_engine is not None
    if durable:
        client_for(store)
    try:
        result = _book(request).accept_webhook(
            token, raw, header, idempotency_header=idem, execute=not durable
        )
    except ConflictError as exc:
        return JSONResponse(status_code=409, content={"event_id": exc.detail})
    if durable and result.get("status") == "accepted":
        event = store.routine_events[uuid.UUID(str(result["event_id"]))]
        if event.get("run_id"):
            await start_run(store, uuid.UUID(str(event["run_id"])))
    return JSONResponse(status_code=202, content={"event_id": result.get("event_id")})


@router.post(
    "/internal/v1/channels/events",
    dependencies=[Depends(require_permission("routines:manage_all"))],
)
@expose(public=False, permission="routines:manage_all")
async def channel_events(body: ChannelEventBody, request: Request) -> dict[str, object]:
    return _book(request).accept_channel(actor(request), dump(body))
