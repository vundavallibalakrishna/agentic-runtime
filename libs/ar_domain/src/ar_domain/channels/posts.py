"""Durable channel posts. OQ-41: the table is the record, flushed with the catalogue."""

import uuid
from typing import TYPE_CHECKING

import orjson

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.channels.metrics import OUTBOUND
from ar_domain.policy.logic import evaluate
from ar_domain.policy.service import active_rules

if TYPE_CHECKING:
    from typing import Any

_TOOLS = {
    "slack": "delivery.slack_post",
    "teams": "delivery.teams_post",
    "email": "delivery.email_send",
    "webhook": "delivery.webhook_post",
}


def _bucket(store: Any, name: str) -> dict[uuid.UUID, dict[str, object]]:
    current = getattr(store, name, None)
    if isinstance(current, dict):
        return current
    fresh: dict[uuid.UUID, dict[str, object]] = {}
    setattr(store, name, fresh)
    return fresh


def policy_decision(store: Any, tenant_id: object, tool: str) -> str:
    """Ask the policy gateway. A missing catalogue allows the call."""
    if not isinstance(tenant_id, uuid.UUID):
        return "allow"
    policies = getattr(store, "policies", None)
    if not isinstance(policies, dict):
        return "allow"
    settings = getattr(store, "tenant_settings", {})
    raw = settings.get(tenant_id) if isinstance(settings, dict) else {}
    document = raw if isinstance(raw, dict) else {}
    decision = evaluate(
        {"tool": {"qualified_name": tool, "risk_class": "W2"}, "agent": {}},
        active_rules(store, tenant_id),
        document,
    )
    return str(decision.get("decision") or "deny")


def record_channel_post(
    store: Any,
    *,
    tenant_id: object,
    kind: str,
    body: str,
    direction: str = "outbound",
    integration_id: object = None,
    thread_id: object = None,
    external_message_id: str = "",
    status: str = "posted",
    detail: dict[str, object] | None = None,
) -> dict[str, object]:
    """Insert one post into the durable catalogue."""
    post_id = new_id()
    row: dict[str, object] = {
        "id": post_id,
        "tenant_id": tenant_id,
        "integration_id": integration_id if isinstance(integration_id, uuid.UUID) else None,
        "thread_id": thread_id if isinstance(thread_id, uuid.UUID) else None,
        "direction": direction,
        "kind": kind,
        "external_message_id": external_message_id or f"{kind}-{post_id.hex[:12]}",
        "body": body,
        "status": status,
        "detail": detail or {},
        "created_at": utcnow(),
    }
    _bucket(store, "channel_posts")[post_id] = row
    if direction == "outbound":
        OUTBOUND.labels(kind=kind or "unknown", result=status).inc()
    return row


def tool_for(kind: str) -> str:
    return _TOOLS.get(kind, "delivery.webhook_post")


def load_credentials(store: Any, integration: dict[str, object]) -> dict[str, object]:
    """Read secret bytes. The public integration view never includes them."""
    values = getattr(store, "secret_values", None)
    if not isinstance(values, dict):
        return {}
    for key in (integration.get("secret_ref_id"), integration.get("id")):
        raw = values.get(key)
        loaded = _parse_secret(raw)
        if loaded:
            return loaded
    return {}


def save_credentials(
    store: Any, integration_id: uuid.UUID, credentials: dict[str, object]
) -> uuid.UUID:
    """Keep credentials in the secret map, addressed by the secret and the integration."""
    secret_id = new_id()
    raw = orjson.dumps(credentials)
    values = getattr(store, "secret_values", None)
    if not isinstance(values, dict):
        values = {}
        store.secret_values = values
    values[secret_id] = raw
    values[integration_id] = raw
    return secret_id


def _parse_secret(raw: object) -> dict[str, object]:
    if isinstance(raw, str):
        raw = raw.encode()
    if not isinstance(raw, bytes) or not raw:
        return {}
    loaded = orjson.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    return {str(key): item for key, item in loaded.items()}
