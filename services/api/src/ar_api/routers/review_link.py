"""One-item review. The token names the approval. A session is required when sign-in is OIDC."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request

from ar_api.auth.mode import AuthMode, resolve_auth_mode
from ar_api.deps import expose
from ar_common.errors import UnauthenticatedError
from ar_contracts.api_model import ApiModel
from ar_domain.approvals.review_link import decide_review, view_approval
from ar_domain.db.context import Principal

router = APIRouter()


class ReviewDecision(ApiModel):
    decision: str
    comment: str = ""
    args_hash: str = ""
    arguments: dict[str, Any] | None = None


def _principal(request: Request) -> Principal | None:
    principal = getattr(request.state, "principal", None)
    return principal if isinstance(principal, Principal) else None


def _session_user(request: Request) -> uuid.UUID | None:
    principal = _principal(request)
    if principal is None or principal.tenant_id is None:
        return None
    try:
        return uuid.UUID(str(principal.id))
    except ValueError:
        return None


def _session_tenant(request: Request) -> uuid.UUID | None:
    principal = _principal(request)
    if principal is None:
        return None
    return principal.tenant_id if isinstance(principal.tenant_id, uuid.UUID) else None


def _require_session(request: Request) -> bool:
    """Production defaults to OIDC, so a token alone is not a credential there."""
    return resolve_auth_mode(request.app.state.settings) is AuthMode.OIDC


@router.get("/api/v1/review/{token}")
@expose(permission=None, public=True)
async def read_review(token: str, request: Request) -> dict[str, object]:
    """The one approval this link names. Other approvals are not returned."""
    require = _require_session(request)
    if require and (_session_user(request) is None or _session_tenant(request) is None):
        raise UnauthenticatedError()
    return view_approval(
        request.app.state.chat,
        token,
        require_session=require,
        session_user_id=_session_user(request),
        session_tenant_id=_session_tenant(request),
    )


@router.post("/api/v1/review/{token}:decide")
@expose(permission=None, public=True)
async def submit_review(token: str, body: ReviewDecision, request: Request) -> dict[str, object]:
    """Approve, reject, or approve with edited arguments."""
    require = _require_session(request)
    return decide_review(
        request.app.state.chat,
        token,
        body.model_dump(by_alias=False),
        require_session=require,
        session_user_id=_session_user(request),
        session_tenant_id=_session_tenant(request),
    )
