"""Shared helpers for the tool HTTP surface."""

from typing import TYPE_CHECKING

from fastapi import Request

from ar_api.actors import actor_from, chat_of, principal_of

if TYPE_CHECKING:
    from ar_contracts.api_model import ApiModel
    from ar_domain.agents.access import Actor
    from ar_domain.chat.service import ChatBehaviour


def chat(request: Request) -> ChatBehaviour:
    return chat_of(request)


def actor(request: Request) -> Actor:
    return actor_from(principal_of(request))


def page(items: list[dict[str, object]]) -> dict[str, object]:
    return {"data": items}


async def load_usage(request: Request) -> None:
    """Load this tenant's stored usage for a usage or quota report.

    The read model does not load usage for every request; a report calls this first so its
    summary sees the metering. It is a no-op without a database.
    """
    from ar_domain.durable.hydrate import load_usage_events  # noqa: PLC0415

    store = chat(request)
    tenant_id = getattr(store, "context_tenant_id", None)
    if tenant_id is not None:
        await load_usage_events(store, tenant_id)


def dump(body: ApiModel) -> dict[str, object]:
    """Snake_case fields for the domain. Public JSON stays camelCase."""
    return body.model_dump(by_alias=False, exclude_unset=True)


def stepped_up(request: Request) -> bool:
    """True when this session completed step-up inside the configured lifetime."""
    from ar_api.auth.step_up import step_up_fresh  # noqa: PLC0415
    from ar_common.time import utcnow  # noqa: PLC0415

    principal = principal_of(request)
    ttl = int(request.app.state.settings.step_up_ttl_s)
    return step_up_fresh(principal.step_up_at, now=utcnow(), ttl_s=ttl)
