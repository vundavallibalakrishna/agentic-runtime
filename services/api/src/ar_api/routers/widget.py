"""Web widget sessions. Spec: docs/03-specs/16-channels.md §7."""

import uuid

from fastapi import APIRouter, Request, Response

from ar_api.deps import expose
from ar_api.routers.tooling import chat
from ar_common.errors import ForbiddenError, NotFoundError, UnauthenticatedError
from ar_contracts.api_model import ApiModel
from ar_domain.channels.book import ChannelBook
from ar_domain.channels.posts import load_credentials
from ar_domain.channels.widget_auth import verify_widget_token, widget_user

router = APIRouter()


class WidgetSessionBody(ApiModel):
    integration_id: uuid.UUID
    token: str


def _integration(request: Request, integration_id: uuid.UUID) -> dict[str, object]:
    row = ChannelBook(chat(request))._integrations().get(integration_id)
    if not isinstance(row, dict) or row.get("kind") != "widget":
        raise NotFoundError()
    return row


@router.get("/api/v1/widget/integrations/{integration_id}")
@expose(public=True, permission=None)
async def widget_frame(integration_id: uuid.UUID, request: Request) -> dict[str, object]:
    """Public frame policy. The integration id is the capability."""
    row = _integration(request, integration_id)
    config = row.get("config") if isinstance(row.get("config"), dict) else {}
    raw = None
    if isinstance(config, dict):
        raw = config.get("allowed_origins")
        if raw is None:
            raw = config.get("allowedOrigins")
    origins = raw if isinstance(raw, list) else []
    return {"allowed_origins": [str(item) for item in origins]}


@router.post("/api/v1/widget/sessions", status_code=204)
@expose(public=True, permission=None)
async def widget_session(body: WidgetSessionBody, request: Request) -> Response:
    row = _integration(request, body.integration_id)
    book = ChannelBook(chat(request))
    tenant_id = row.get("tenant_id")
    if not isinstance(tenant_id, uuid.UUID) or not book._enabled(tenant_id, "widget"):
        raise ForbiddenError("the plan does not include widget")
    credentials = load_credentials(chat(request), row)
    secret = str(credentials.get("widget_secret") or credentials.get("secret") or "")
    claims = verify_widget_token(body.token, secret, f"ar-widget:{body.integration_id}")
    if claims is None:
        raise UnauthenticatedError()
    user_id = widget_user(chat(request), tenant_id, str(claims.get("sub") or ""))
    if user_id is None:
        raise UnauthenticatedError()
    response = Response(status_code=204)
    cookie = (
        f"ar_widget_session={user_id}; HttpOnly; Secure; SameSite=None; "
        "Partitioned; Path=/; Max-Age=600"
    )
    response.headers.append("set-cookie", cookie)
    return response
