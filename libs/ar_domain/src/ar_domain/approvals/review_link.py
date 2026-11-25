"""A signed, expiring link to one pending approval.

The token names the approval, the tenant and one approver. It does not grant a
session and it does not satisfy step-up. Outside dev and CI the install's
sign-in is OIDC, so the session user and tenant must be the ones named in the
token. Guests are never approvers.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import orjson

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, UnauthenticatedError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS

if TYPE_CHECKING:
    from typing import Any

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
    """A key derived for review links, not the raw cursor secret."""
    from ar_common.settings import cursor_secret_text  # noqa: PLC0415

    return hmac.new(cursor_secret_text().encode(), b"purpose:review", hashlib.sha256).digest()


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
        "purpose": "review",
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
    if str(loaded.get("purpose") or "") != "review":
        return None
    if _expired(loaded.get("exp")):
        return None
    approval_id = str(loaded.get("approval_id") or "")
    tenant_id = str(loaded.get("tenant_id") or "")
    user_id = str(loaded.get("user_id") or "")
    if not approval_id or not tenant_id or not user_id:
        return None
    return {"approval_id": approval_id, "tenant_id": tenant_id, "user_id": user_id}


def _expired(value: object) -> bool:
    """True when ``exp`` is missing, unreadable, or not in the future."""
    if not isinstance(value, str) or not value:
        return True
    try:
        exp = datetime.fromisoformat(value)
    except ValueError:
        return True
    if exp.tzinfo is None:
        from datetime import UTC  # noqa: PLC0415

        exp = exp.replace(tzinfo=UTC)
    return exp <= utcnow()


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


def view_approval(
    store: Any,
    token: str,
    *,
    require_session: bool = False,
    session_user_id: uuid.UUID | None = None,
    session_tenant_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """One pending approval for the review page. Nothing else is included."""
    claims = read_review_token(token)
    if claims is None:
        raise NotFoundError("review link not found")
    _session_matches(
        claims,
        require_session=require_session,
        session_user_id=session_user_id,
        session_tenant_id=session_tenant_id,
    )
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
    """The named approver. A disabled user, or one with no role, cannot decide."""
    user = _user(store, user_id)
    if str(user.get("status") or "") != "active":
        raise ForbiddenError("this approver is not active")
    roles: set[str] = set()
    held = getattr(store, "user_roles", {})
    if isinstance(held, dict):
        found = held.get(user_id) or held.get(str(user_id)) or set()
        roles = {str(item) for item in found}
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
        auth_method="review_link",
    )


def decide_review(
    store: Any,
    token: str,
    body: dict[str, object],
    *,
    require_session: bool,
    session_user_id: uuid.UUID | None,
    session_tenant_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """Approve, reject, or approve with edited arguments. Both versions are kept.

    A review link never counts as step-up. An approval that requires step-up
    stays pending until a signed-in session completes it.
    """
    claims = read_review_token(token)
    if claims is None:
        raise NotFoundError("review link not found")
    user_id = _uuid(claims["user_id"])
    tenant_id = _uuid(claims["tenant_id"])
    approval_id = _uuid(claims["approval_id"])
    if user_id is None or tenant_id is None or approval_id is None:
        raise NotFoundError("review link not found")
    _session_matches(
        claims,
        require_session=require_session,
        session_user_id=session_user_id,
        session_tenant_id=session_tenant_id,
    )
    row = _approval(store, claims)
    if str(row.get("status") or "") != "pending":
        raise ConflictError("approval is not pending")
    from ar_domain.approvals.logic import is_approver  # noqa: PLC0415
    from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

    actor = actor_for(store, tenant_id, user_id)
    if not is_approver(store, actor, row):
        raise ForbiddenError("this person is not an approver for this request")
    decision: dict[str, object] = {
        "decision": str(body.get("decision") or ""),
        "comment": str(body.get("comment") or body.get("reason") or ""),
        "args_hash": str(body.get("args_hash") or row.get("args_hash") or ""),
    }
    edited = body.get("arguments")
    if isinstance(edited, dict) and edited:
        decision["arguments"] = edited
    return ApprovalBook(store).decide(
        actor,
        approval_id,
        decision,
        stepped_up=False,
        channel="review_link",
    )


def _session_matches(
    claims: dict[str, str],
    *,
    require_session: bool,
    session_user_id: uuid.UUID | None,
    session_tenant_id: uuid.UUID | None,
) -> None:
    if not require_session:
        return
    if session_user_id is None or session_tenant_id is None:
        raise UnauthenticatedError()
    if str(session_user_id) != claims["user_id"] or str(session_tenant_id) != claims["tenant_id"]:
        raise ForbiddenError("this review link is for someone else")


def _user(store: Any, user_id: uuid.UUID) -> dict[str, object]:
    statuses = getattr(store, "user_statuses", {})
    status = statuses.get(user_id) if isinstance(statuses, dict) else None
    if status is None and isinstance(statuses, dict):
        status = statuses.get(str(user_id))
    return {"status": str(status or "")}
