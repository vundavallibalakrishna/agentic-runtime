"""A signed, expiring link to one pending approval.

The token names the approval, the tenant and one approver. It does not grant a
session. When the install requires a session, the caller must already be that
approver. Otherwise the token is the credential and the decision is attributed
to the named approver. Guests are never approvers.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from typing import TYPE_CHECKING, Any

import orjson

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, UnauthenticatedError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS

if TYPE_CHECKING:
    from datetime import datetime

_DEFAULT_BASE = "http://localhost:3000"


def public_base() -> str:
    """The web origin. ``AR_PUBLIC_URL`` is the install setting."""
    raw = os.environ.get("AR_PUBLIC_URL", _DEFAULT_BASE).strip().rstrip("/")
    return raw or _DEFAULT_BASE


def review_url(token: str) -> str:
    return f"{public_base()}/review/{token}"


def link_deadline(approval_expires: datetime) -> datetime:
    """The earlier of the approval expiry and ``AR_REVIEW_LINK_TTL_S``."""
    raw = os.environ.get("AR_REVIEW_LINK_TTL_S", "86400").strip() or "86400"
    try:
        seconds = max(60, int(raw))
    except ValueError:
        seconds = 86400
    from datetime import timedelta  # noqa: PLC0415

    cap = utcnow() + timedelta(seconds=seconds)
    return approval_expires if approval_expires <= cap else cap


def _secret() -> bytes:
    from ar_common.settings import cursor_secret_text  # noqa: PLC0415

    return cursor_secret_text().encode()


def issue_review_token(
    approval_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> str:
    """HMAC token. Expired or altered tokens do not read."""
    payload = {
        "approval_id": str(approval_id),
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "exp": expires_at.isoformat(),
    }
    body = orjson.dumps(payload)
    digest = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    return f"{body.hex()}.{digest}"


def read_review_token(token: str) -> dict[str, str] | None:  # noqa: PLR0911
    """Claims, or None when the token is forged or expired."""
    body_hex, dot, digest = token.partition(".")
    if not dot or not body_hex or not digest:
        return None
    try:
        body = bytes.fromhex(body_hex)
    except ValueError:
        return None
    expected = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, digest):
        return None
    loaded = orjson.loads(body)
    if not isinstance(loaded, dict):
        return None
    exp = str(loaded.get("exp") or "")
    if not exp or exp <= utcnow().isoformat():
        return None
    approval_id = str(loaded.get("approval_id") or "")
    tenant_id = str(loaded.get("tenant_id") or "")
    user_id = str(loaded.get("user_id") or "")
    if not approval_id or not tenant_id or not user_id:
        return None
    return {"approval_id": approval_id, "tenant_id": tenant_id, "user_id": user_id}


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _approval(store: Any, claims: dict[str, str]) -> dict[str, object]:
    approval_id = _uuid(claims["approval_id"])
    tenant_id = _uuid(claims["tenant_id"])
    approvals = getattr(store, "approvals", {})
    row = approvals.get(approval_id) if isinstance(approvals, dict) and approval_id else None
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        raise NotFoundError("approval not found")
    return row


def input_schema(store: Any, row: dict[str, object]) -> dict[str, object]:
    """The tool's input schema, or a schema read off the arguments themselves."""
    preview = row.get("preview")
    if isinstance(preview, dict) and isinstance(preview.get("schema"), dict):
        return preview["schema"]
    name = str(row.get("qualified_name") or "")
    versions = getattr(store, "tool_versions", {})
    if isinstance(versions, dict):
        for item in versions.values():
            if isinstance(item, dict) and str(item.get("qualified_name") or "") == name:
                schema = item.get("input_schema")
                if isinstance(schema, dict) and schema:
                    return schema
    return _schema_of(row.get("arguments"))


def _schema_of(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {"type": "object", "properties": {}}
    properties: dict[str, object] = {}
    for key, item in value.items():
        properties[str(key)] = _schema_value(item)
    return {"type": "object", "properties": properties, "additionalProperties": True}


def _schema_value(value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, list):
        item = _schema_value(value[0]) if value else {"type": "string"}
        return {"type": "array", "items": item}
    if isinstance(value, dict):
        return _schema_of(value)
    return {"type": "string"}


def view_approval(store: Any, token: str) -> dict[str, object]:
    """One pending approval for the review page. Nothing else is included."""
    claims = read_review_token(token)
    if claims is None:
        raise NotFoundError("review link not found")
    row = _approval(store, claims)
    arguments = row.get("arguments")
    preview = row.get("preview")
    return {
        "approval_id": str(row.get("id")),
        "tenant_id": claims["tenant_id"],
        "user_id": claims["user_id"],
        "qualified_name": str(row.get("qualified_name") or ""),
        "status": str(row.get("status") or ""),
        "arguments": arguments if isinstance(arguments, dict) else {},
        "schema": input_schema(store, row),
        "preview": preview if isinstance(preview, dict) else {},
        "args_hash": str(row.get("args_hash") or ""),
        "step_up_required": bool(row.get("step_up_required")),
    }


def actor_for(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Actor:
    """The named approver, with permission to decide this one item."""
    roles: set[str] = set()
    held = getattr(store, "user_roles", {})
    if isinstance(held, dict):
        found = held.get(user_id) or held.get(str(user_id)) or set()
        roles = {str(item) for item in found}
    permissions: set[str] = set()
    for role in roles:
        permissions.update(SYSTEM_ROLE_PERMISSIONS.get(role, ()))
    permissions.add("approvals:decide")
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
        auth_method="review_link",
    )


def decide_review(
    store: Any,
    token: str,
    body: dict[str, object],
    *,
    require_session: bool,
    session_user_id: uuid.UUID | None,
    stepped_up: bool,
) -> dict[str, object]:
    """Approve, reject, or approve with edited arguments. Both versions are kept."""
    claims = read_review_token(token)
    if claims is None:
        raise NotFoundError("review link not found")
    user_id = _uuid(claims["user_id"])
    tenant_id = _uuid(claims["tenant_id"])
    approval_id = _uuid(claims["approval_id"])
    if user_id is None or tenant_id is None or approval_id is None:
        raise NotFoundError("review link not found")
    if require_session:
        if session_user_id is None:
            raise UnauthenticatedError()
        if session_user_id != user_id:
            raise ForbiddenError("this review link is for someone else")
    row = _approval(store, claims)
    if str(row.get("status") or "") != "pending":
        raise ConflictError("approval is not pending")
    from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

    decision: dict[str, object] = {
        "decision": str(body.get("decision") or ""),
        "comment": str(body.get("comment") or body.get("reason") or ""),
        "args_hash": str(body.get("args_hash") or row.get("args_hash") or ""),
    }
    edited = body.get("arguments")
    if isinstance(edited, dict) and edited:
        decision["arguments"] = edited
    return ApprovalBook(store).decide(
        actor_for(store, tenant_id, user_id),
        approval_id,
        decision,
        stepped_up=stepped_up or not bool(row.get("step_up_required")),
        channel="review_link",
    )
