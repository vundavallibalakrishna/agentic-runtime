"""A Slack workspace the channels page can open immediately."""

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.channels.posts import record_channel_post, save_credentials
from ar_domain.chat.service import demo_id

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def seed_channels(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Insert one Slack integration and a durable post. Stable ids stay idempotent."""
    integration_id = demo_id("channel-slack")
    if integration_id in store.channel_integrations:
        return
    agent = store.ensure_assistant(tenant_id, user_id)
    _open_assistant(store, agent)
    now = utcnow()
    secret_id = save_credentials(
        store,
        integration_id,
        {"bot_token": "xoxb-demo", "signing_secret": "demo-signing-secret"},
    )
    store.channel_integrations[integration_id] = {
        "id": integration_id,
        "tenant_id": tenant_id,
        "kind": "slack",
        "name": "Workspace Slack",
        "config": {"command": "/agent", "allowed_channel_ids": []},
        "secret_ref_id": secret_id,
        "default_agent_id": agent["id"],
        "agent_routing": [{"match": {"channel_id": "C-PLATFORM"}, "agent_id": str(agent["id"])}],
        "status": "active",
        "status_detail": "",
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    identity_id = demo_id("channel-identity-admin")
    store.channel_identities[identity_id] = {
        "id": identity_id,
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "external_user_id": "U-ADMIN",
        "user_id": user_id,
        "match_method": "manual_link",
        "verified_at": now,
        "created_at": now,
    }
    record_channel_post(
        store,
        tenant_id=tenant_id,
        kind="slack",
        body="The weekly digest is ready for #platform.",
        integration_id=integration_id,
        external_message_id="slack-demo-digest",
        detail={"routine": "Weekly digest", "channel": "#platform"},
    )


def _open_assistant(store: ChatService, agent: dict[str, object]) -> None:
    """The seeded assistant answers Slack, Teams and email. The factory default stays closed."""
    version_id = agent.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    if not isinstance(version, dict):
        return
    definition = version.get("definition")
    opened = {"slack": True, "teams": True, "email": True}
    if isinstance(definition, dict):
        current = definition.get("channels")
        channels = dict(current) if isinstance(current, dict) else {}
        channels.update(opened)
        definition["channels"] = channels
        return
    copy = getattr(definition, "model_copy", None)
    channel_set = getattr(definition, "channels", None)
    channel_copy = getattr(channel_set, "model_copy", None)
    if not callable(copy) or not callable(channel_copy):
        return
    version["definition"] = copy(update={"channels": channel_copy(update=opened)})
