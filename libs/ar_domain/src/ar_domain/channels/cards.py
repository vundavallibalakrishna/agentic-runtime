"""Record an approval card on every Slack or Teams binding for its approvers.

The channels service is what talks to Slack and Teams. This module records the
card the product keeps, and asks that service to deliver it when the install
has named the service (``AR_CHANNELS_URL``).
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

from ar_common.approval_cards import slack_blocks, teams_card
from ar_domain.approvals.review_link import issue_review_token, link_deadline, review_url
from ar_domain.channels.posts import load_credentials, record_channel_post

if TYPE_CHECKING:
    from typing import Any

_KINDS = frozenset({"slack", "teams"})


def links_for(store: Any, row: dict[str, object], approver_ids: list[str]) -> dict[str, str]:  # noqa: ARG001
    """One review link per approver. The token expires with the approval."""
    approval_id = row.get("id")
    tenant_id = row.get("tenant_id")
    expires = row.get("expires_at")
    if not isinstance(approval_id, uuid.UUID) or not isinstance(tenant_id, uuid.UUID):
        return {}
    from datetime import datetime  # noqa: PLC0415

    if not isinstance(expires, datetime):
        return {}
    found: dict[str, str] = {}
    for user_id in approver_ids:
        try:
            person = uuid.UUID(user_id)
        except ValueError:
            continue
        token = issue_review_token(approval_id, tenant_id, person, link_deadline(expires))
        found[user_id] = review_url(token)
    return found


def post_cards(
    store: Any, row: dict[str, object], approver_ids: list[str], links: dict[str, str]
) -> list[dict[str, object]]:
    """A card for each binding. No binding means nothing is posted."""
    posted: list[dict[str, object]] = []
    for integration, identity in _bindings(store, row, approver_ids):
        kind = str(integration.get("kind") or "")
        user_id = ""
        if isinstance(identity, dict):
            user_id = str(identity.get("user_id") or "")
        link = links.get(user_id) or next(iter(links.values()), "")
        text = f"Approval requested for {row.get('qualified_name') or 'a tool'}"
        card = _card(row, kind, link, text)
        detail = {
            "approval_id": str(row.get("id") or ""),
            "args_hash": str(row.get("args_hash") or ""),
            "review_url": link,
            "card": card,
            "step_up": bool(row.get("step_up_required")),
        }
        record_channel_post(
            store,
            tenant_id=row.get("tenant_id"),
            kind=kind,
            body=text,
            integration_id=integration.get("id"),
            detail=detail,
            status="posted",
        )
        delivered = _ask_channels(store, integration, identity, detail, text)
        posted.append({"kind": kind, "review_url": link, "delivered": delivered})
    return posted


def _card(row: dict[str, object], kind: str, link: str, text: str) -> dict[str, object]:
    approval_id = str(row.get("id") or "")
    args_hash = str(row.get("args_hash") or "")
    step_up = bool(row.get("step_up_required"))
    if kind == "teams":
        return teams_card(
            text, approval_id=approval_id, args_hash=args_hash, step_up=step_up, web_url=link
        )
    return {
        "text": text,
        "blocks": slack_blocks(approval_id, args_hash, step_up=step_up, web_url=link),
    }


def _bindings(  # noqa: PLR0912
    store: Any, row: dict[str, object], approver_ids: list[str]
) -> list[tuple[dict[str, object], dict[str, object] | None]]:
    tenant_id = row.get("tenant_id")
    integrations = getattr(store, "channel_integrations", {})
    identities = getattr(store, "channel_identities", {})
    if not isinstance(integrations, dict):
        return []
    wanted = set(approver_ids)
    found: list[tuple[dict[str, object], dict[str, object] | None]] = []
    seen: set[object] = set()
    if isinstance(identities, dict):
        for identity in identities.values():
            if not isinstance(identity, dict):
                continue
            if str(identity.get("tenant_id")) != str(tenant_id):
                continue
            if str(identity.get("user_id")) not in wanted:
                continue
            integration = integrations.get(identity.get("integration_id"))
            if not isinstance(integration, dict):
                continue
            if str(integration.get("kind") or "") not in _KINDS:
                continue
            if integration.get("status") == "disabled":
                continue
            found.append((integration, identity))
            seen.add(integration.get("id"))
    if found:
        return found
    for integration in integrations.values():
        if not isinstance(integration, dict):
            continue
        if str(integration.get("tenant_id")) != str(tenant_id):
            continue
        if integration.get("status") == "disabled":
            continue
        if str(integration.get("kind") or "") not in _KINDS:
            continue
        if integration.get("id") in seen:
            continue
        found.append((integration, None))
    return found


def _ask_channels(
    store: Any,
    integration: dict[str, object],
    identity: dict[str, object] | None,
    detail: dict[str, object],
    text: str,
) -> str:
    base = os.environ.get("AR_CHANNELS_URL", "").strip().rstrip("/")
    if not base:
        return "recorded"
    body = {
        "kind": str(integration.get("kind") or ""),
        "integration_id": str(integration.get("id") or ""),
        "approval_id": detail.get("approval_id"),
        "args_hash": detail.get("args_hash"),
        "step_up": detail.get("step_up"),
        "review_url": detail.get("review_url"),
        "text": text,
        "external_user_id": "" if identity is None else str(identity.get("external_user_id") or ""),
        "credentials": load_credentials(store, integration),
    }
    try:
        from ar_common.internal_http import internal_post  # noqa: PLC0415

        response = internal_post(f"{base}/internal/v1/outbound", json=body, timeout=5.0)
    except Exception:  # noqa: BLE001 — a down channels process leaves the recorded card
        return "channels_unreachable"
    if response.status_code >= 300:
        return "channels_rejected"
    return "sent"
