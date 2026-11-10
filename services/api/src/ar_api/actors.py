"""Map an authenticated principal onto the in-memory product store."""

import uuid

from fastapi import Request

from ar_common.errors import NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatBehaviour
from ar_domain.db.context import Principal


def chat_of(request: Request) -> ChatBehaviour:
    unit = getattr(request.state, "read_unit", None)
    if isinstance(unit, ChatBehaviour):
        return unit
    service = request.app.state.chat
    if isinstance(service, ChatBehaviour):
        return service
    raise NotFoundError()


def principal_of(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal) or principal.tenant_id is None:
        raise NotFoundError()
    return principal


def actor_from(principal: Principal) -> Actor:
    if principal.tenant_id is None:
        raise NotFoundError()
    teams = frozenset(str(team_id) for team_id, _permission in principal.team_permissions)
    return Actor(
        tenant_id=principal.tenant_id,
        user_id=uuid.UUID(principal.id),
        permissions=principal.permissions,
        team_ids=teams,
        display_name=principal.display_name or principal.email or "User",
        roles=principal.roles,
        auth_method=principal.auth_method,
        step_up_at=principal.step_up_at,
        kind=principal.kind,
        support_level=principal.support_level,
    )
