"""Inbound channel messages. Spec: docs/03-specs/16-channels.md §3."""

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError
from ar_common.time import utcnow
from ar_domain.agents.logic import AgentView, can_see_agent
from ar_domain.channels.book import ChannelBook, issue_for
from ar_domain.channels.metrics import INBOUND, LINK_REQUIRED
from ar_domain.channels.posts import record_channel_post

if TYPE_CHECKING:
    from typing import Any


def handle_inbound(
    store: Any, message: dict[str, object], *, schedule: bool = True
) -> dict[str, object]:
    """Resolve the person, pick an agent, and start a run."""
    integration = _integration(store, message.get("integration_id"))
    kind = str(message.get("kind") or integration.get("kind") or "slack")
    identity = _identity(store, integration, message)
    if identity is None:
        LINK_REQUIRED.labels(kind=kind).inc()
        INBOUND.labels(kind=kind, result="link_required").inc()
        token = issue_for(
            store, _must_uuid(integration.get("id")), str(message.get("external_user_id") or "")
        )
        return {
            "action": "link_required",
            "link_url": f"/settings/profile?link={token}",
        }
    user_id = _must_uuid(identity.get("user_id"))
    agent = _select_agent(store, integration, message, user_id)
    if agent is None:
        INBOUND.labels(kind=kind, result="no_agent").inc()
        return {"action": "no_agent", "detail": "no agent is available in this channel"}
    thread = _thread(store, integration, message, user_id, _must_uuid(agent.get("id")))
    conversation_id = _must_uuid(thread.get("conversation_id"))
    conversation = store.conversations.get(conversation_id)
    if isinstance(conversation, dict) and _busy(store, conversation):
        INBOUND.labels(kind=kind, result="busy").inc()
        return {"action": "busy", "detail": "Still working on the previous request"}
    text = str(message.get("text") or "")
    posted = store.post_message(
        _must_uuid(integration.get("tenant_id")),
        user_id,
        conversation_id,
        text,
        schedule=schedule,
    )
    if isinstance(conversation, dict):
        conversation["channel"] = kind
    run = posted.get("run") if isinstance(posted, dict) else None
    run_id = run.get("id") if isinstance(run, dict) else None
    record_channel_post(
        store,
        tenant_id=integration.get("tenant_id"),
        kind=kind,
        body=text,
        direction="inbound",
        integration_id=integration.get("id"),
        thread_id=thread.get("id"),
        external_message_id=str(
            message.get("external_message_id") or message.get("event_id") or ""
        ),
    )
    INBOUND.labels(kind=kind, result="accepted").inc()
    return {"conversation_id": str(conversation_id), "run_id": str(run_id)}


def decide_approval(store: Any, body: dict[str, object]) -> dict[str, object]:
    """Decide a Slack or Teams approval on the same path as the web inbox.

    The button names an external user. That user is mapped to a person in the
    tenant, and ``ApprovalBook.decide`` applies eligibility, separation of duties,
    the args hash and the audit row. A click that is not linked to a person is
    refused.
    """
    approval_id = _uuid(body.get("approval_id"))
    approvals = getattr(store, "approvals", {})
    row = approvals.get(approval_id) if isinstance(approvals, dict) and approval_id else None
    if not isinstance(row, dict) or approval_id is None:
        raise NotFoundError()
    decision = str(body.get("decision") or "")
    if decision not in {"approve", "reject"}:
        return {"result": "ignored"}
    actor = _approval_actor(store, body, row)
    if actor is None:
        return {"result": "unlinked", "approval_id": str(approval_id)}
    from ar_common.errors import ConflictError, ForbiddenError, ValidationFailedError  # noqa: PLC0415
    from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

    channel = str(body.get("kind") or body.get("channel") or "slack")
    try:
        detail = ApprovalBook(store).decide(
            actor,
            approval_id,
            {
                "decision": decision,
                "args_hash": str(body.get("args_hash") or ""),
                "comment": str(body.get("comment") or ""),
            },
            stepped_up=bool(body.get("stepped_up")),
            channel=channel,
        )
    except (ConflictError, ForbiddenError, ValidationFailedError) as exc:
        return _approval_error(exc, approval_id)
    status = str(detail.get("status") or "")
    if status == "approved":
        from ar_domain.routines.engine import release_delivery  # noqa: PLC0415

        release_delivery(store, approval_id)
    return {"result": status, "approval_id": str(approval_id)}


def _approval_error(exc: Exception, approval_id: uuid.UUID) -> dict[str, object]:
    """Map a decide failure onto the channel result the button handler returns."""
    from ar_common.errors import ConflictError, ForbiddenError, ValidationFailedError  # noqa: PLC0415
    from ar_domain.approvals.errors import StepUpRequiredError  # noqa: PLC0415

    ref = str(approval_id)
    if isinstance(exc, ConflictError):
        if "args" in exc.detail:
            return {"result": "args_mismatch", "approval_id": ref}
        return {"result": "conflict", "approval_id": ref, "detail": exc.detail}
    if isinstance(exc, StepUpRequiredError):
        return {"result": "step_up_required", "approval_id": ref}
    if isinstance(exc, ForbiddenError):
        return {"result": "forbidden", "approval_id": ref}
    if isinstance(exc, ValidationFailedError) and exc.detail == "sod_violation":
        return {"result": "sod_violation", "approval_id": ref}
    detail = exc.detail if isinstance(exc, ValidationFailedError) else ""
    return {"result": "invalid", "approval_id": ref, "detail": detail}


def _approval_actor(store: Any, body: dict[str, object], row: dict[str, object]) -> Any:
    """The person who pressed the button, or None when they are not linked."""
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS  # noqa: PLC0415

    user_id = _linked_user(store, body, row)
    tenant_id = _uuid(row.get("tenant_id"))
    if user_id is None or tenant_id is None:
        return None
    roles = _roles_for(store, user_id)
    permissions: set[str] = set()
    for role in roles:
        permissions.update(SYSTEM_ROLE_PERMISSIONS.get(role, ()))
    names = getattr(store, "display_names", {})
    display = "User"
    if isinstance(names, dict):
        display = str(names.get(user_id) or names.get(str(user_id)) or "User")
    return Actor(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=frozenset(permissions),
        roles=frozenset(roles),
        display_name=display,
        auth_method="bearer",
    )


def _linked_user(store: Any, body: dict[str, object], row: dict[str, object]) -> uuid.UUID | None:
    """Map the channel user onto a person in the approval's tenant."""
    tenant_id = row.get("tenant_id")
    integration_id = _uuid(body.get("integration_id"))
    external = str(body.get("external_user_id") or "")
    if integration_id is not None and external:
        for identity in ChannelBook(store)._identities().values():
            if identity.get("integration_id") != integration_id:
                continue
            if identity.get("external_user_id") != external:
                continue
            if identity.get("tenant_id") != tenant_id:
                continue
            return _uuid(identity.get("user_id"))
    email = str(body.get("external_user_email") or "").lower()
    if not email:
        return None
    user_id = _user_for_email(store, email)
    if user_id is None:
        return None
    emails = getattr(store, "user_tenants", {})
    if isinstance(emails, dict) and emails.get(user_id) not in {None, tenant_id}:
        return None
    return user_id


def _roles_for(store: Any, user_id: uuid.UUID) -> set[str]:
    raw = getattr(store, "user_roles", {})
    if not isinstance(raw, dict):
        return set()
    held = raw.get(user_id)
    if held is None:
        held = raw.get(str(user_id))
    if isinstance(held, (set, frozenset, list, tuple)):
        return {str(item) for item in held}
    return set()


def _integration(store: Any, raw: object) -> dict[str, object]:
    integration_id = _uuid(raw)
    book = ChannelBook(store)
    rows = book._integrations()
    row = rows.get(integration_id) if integration_id else None
    if not isinstance(row, dict):
        raise NotFoundError()
    return row


def _identity(
    store: Any, integration: dict[str, object], message: dict[str, object]
) -> dict[str, object] | None:
    external = str(message.get("external_user_id") or "")
    integration_id = integration.get("id")
    for row in ChannelBook(store)._identities().values():
        if row.get("integration_id") == integration_id and row.get("external_user_id") == external:
            return row
    email = str(message.get("external_user_email") or "").lower()
    if not email:
        return None
    user_id = _user_for_email(store, email)
    if user_id is None:
        return None
    identity_id = uuid.uuid4()
    row = {
        "id": identity_id,
        "tenant_id": integration.get("tenant_id"),
        "integration_id": integration_id,
        "external_user_id": external,
        "user_id": user_id,
        "match_method": "email",
        "verified_at": utcnow(),
        "created_at": utcnow(),
    }
    ChannelBook(store)._identities()[identity_id] = row
    return row


def _user_for_email(store: Any, email: str) -> uuid.UUID | None:
    """The person with this address among the tenant's people the store holds."""
    emails = getattr(store, "user_emails", {})
    if isinstance(emails, dict):
        for user_id, value in emails.items():
            if str(value).lower() == email and isinstance(user_id, uuid.UUID):
                return user_id
    return None


def _select_agent(
    store: Any, integration: dict[str, object], message: dict[str, object], user_id: uuid.UUID
) -> dict[str, object] | None:
    command = message.get("command")
    slug = ""
    if isinstance(command, dict):
        slug = str(command.get("agent_slug") or "")
    if slug:
        found = _by_slug(store, integration.get("tenant_id"), slug)
        if found is not None and _visible(store, found, user_id, str(message.get("kind") or "")):
            return found
    text = str(message.get("text") or "")
    channel_id = str(message.get("external_channel_id") or "")
    routing = integration.get("agent_routing")
    rules = routing if isinstance(routing, list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") if isinstance(rule.get("match"), dict) else {}
        agent_id = _uuid(rule.get("agent_id"))
        if not isinstance(match, dict) or agent_id is None:
            continue
        channel_match = str(match.get("channel_id") or "")
        keyword = str(match.get("keyword") or "")
        if channel_match and channel_match != channel_id:
            continue
        if keyword and not text.lower().startswith(keyword.lower()):
            continue
        agent = store.agents.get(agent_id)
        if isinstance(agent, dict) and _visible(
            store, agent, user_id, str(message.get("kind") or "")
        ):
            return agent
    default_id = integration.get("default_agent_id")
    if isinstance(default_id, uuid.UUID):
        agent = store.agents.get(default_id)
        if isinstance(agent, dict) and _visible(
            store, agent, user_id, str(message.get("kind") or "")
        ):
            return agent
    return None


def _by_slug(store: Any, tenant_id: object, slug: str) -> dict[str, object] | None:
    agents = getattr(store, "agents", {})
    if not isinstance(agents, dict):
        return None
    for agent in agents.values():
        if not isinstance(agent, dict):
            continue
        if agent.get("tenant_id") == tenant_id and agent.get("slug") == slug:
            return agent
    return None


def _visible(store: Any, agent: dict[str, object], user_id: uuid.UUID, kind: str) -> bool:
    if not _channel_open(store, agent, kind):
        return False
    view = AgentView(
        tenant_id=str(agent.get("tenant_id")),
        owner_user_id=None
        if agent.get("owner_user_id") is None
        else str(agent.get("owner_user_id")),
        owner_team_id=None
        if agent.get("owner_team_id") is None
        else str(agent.get("owner_team_id")),
        visibility=str(agent.get("visibility") or "tenant"),
        status=str(agent.get("status") or "active"),
        disabled=bool(agent.get("disabled")),
    )
    return can_see_agent(
        view,
        tenant_id=str(agent.get("tenant_id")),
        user_id=str(user_id),
        team_ids=set(),
        manage_all=True,
    )


def _channel_open(store: Any, agent: dict[str, object], kind: str) -> bool:
    version_id = agent.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    channels = getattr(definition, "channels", None)
    if channels is None and isinstance(definition, dict):
        channels = definition.get("channels")
    if channels is None:
        return kind == "api"
    if isinstance(channels, dict):
        return bool(channels.get(kind))
    return bool(getattr(channels, kind, False))


def _thread(
    store: Any,
    integration: dict[str, object],
    message: dict[str, object],
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> dict[str, object]:
    channel_id = str(message.get("external_channel_id") or "dm")
    thread_id = str(
        message.get("external_thread_id") or message.get("external_message_id") or channel_id
    )
    integration_id = integration.get("id")
    threads = getattr(store, "channel_threads", None)
    if not isinstance(threads, dict):
        threads = {}
        store.channel_threads = threads
    for row in threads.values():
        if (
            isinstance(row, dict)
            and row.get("integration_id") == integration_id
            and row.get("external_channel_id") == channel_id
            and row.get("external_thread_id") == thread_id
        ):
            return row
    conversation = store.create_conversation(
        _must_uuid(integration.get("tenant_id")), user_id, agent_id
    )
    conversation_id = _uuid(conversation.get("id"))
    if isinstance(conversation_id, uuid.UUID):
        stored = store.conversations.get(conversation_id)
        if isinstance(stored, dict):
            stored["channel"] = str(message.get("kind") or integration.get("kind"))
    row = {
        "id": uuid.uuid4(),
        "tenant_id": integration.get("tenant_id"),
        "integration_id": integration_id,
        "external_channel_id": channel_id,
        "external_thread_id": thread_id,
        "conversation_id": conversation_id,
        "created_at": utcnow(),
    }
    threads[row["id"]] = row
    return row


def _busy(store: Any, conversation: dict[str, object]) -> bool:
    active = conversation.get("active_run_id")
    if not isinstance(active, uuid.UUID):
        return False
    run = store.runs.get(active)
    if not isinstance(run, dict):
        return False
    return str(run.get("status")) in {"queued", "running", "waiting_approval", "waiting_input"}


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _must_uuid(value: object) -> uuid.UUID:
    found = _uuid(value)
    if found is None:
        raise NotFoundError()
    return found
