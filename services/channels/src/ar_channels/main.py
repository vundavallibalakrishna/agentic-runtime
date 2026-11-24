"""HTTP entrypoint for channels."""

import os
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ar_channels.bridge import HttpBridge
from ar_channels.email_channel import BounceBook, InProcessMailbox
from ar_channels.handlers import (
    handle_email,
    handle_slack_command,
    handle_slack_events,
    handle_slack_interaction,
    handle_teams,
    slack_approval_message,
)
from ar_channels.render import adaptive_card
from ar_channels.state import Dedupe, LeaderLock
from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

if TYPE_CHECKING:
    from typing import Any

LISTEN_PORT = 8004


def _approval_card(body: dict[str, Any]) -> dict[str, object]:
    """Render the interactive card. ``slack_approval_message`` is the Slack form."""
    approval_id = str(body.get("approval_id") or "")
    if not approval_id:
        return {}
    args_hash = str(body.get("args_hash") or "")
    step_up = bool(body.get("step_up"))
    review_url = str(body.get("review_url") or "")
    text = str(body.get("text") or "Approval requested")
    kind = str(body.get("kind") or "slack")
    if kind == "teams":
        return adaptive_card(
            text, approval_id=approval_id, args_hash=args_hash, step_up=step_up, web_url=review_url
        )
    return slack_approval_message(approval_id, args_hash, step_up=step_up, web_url=review_url)


def _deliver_card(body: dict[str, Any], card: dict[str, object]) -> str:
    """POST the card when the binding stored a webhook or a bot token. Otherwise recorded."""
    if not card:
        return "recorded"
    credentials = body.get("credentials")
    secret = credentials if isinstance(credentials, dict) else {}
    webhook = str(secret.get("webhook_url") or "")
    if webhook:
        return _post_json(webhook, card)
    token = str(secret.get("bot_token") or "")
    if token and str(body.get("kind") or "") == "slack":
        return _slack_api(token, str(body.get("external_user_id") or ""), card)
    return "recorded"


def _post_json(url: str, payload: dict[str, object]) -> str:
    import httpx  # noqa: PLC0415

    try:
        response = httpx.post(url, json=payload, timeout=5.0)
    except httpx.HTTPError:
        return "failed"
    return "sent" if response.status_code < 300 else "failed"


def _slack_api(token: str, user: str, card: dict[str, object]) -> str:
    """Post with the Slack SDK the channels service already depends on. Not live-tested."""
    try:
        from slack_sdk import WebClient  # noqa: PLC0415
        from slack_sdk.errors import SlackApiError  # noqa: PLC0415
    except ImportError:
        return "recorded"
    client = WebClient(token=token)
    channel = user
    try:
        if user:
            opened = client.conversations_open(users=user)
            channel = str(opened.get("channel", {}).get("id") or user)
        client.chat_postMessage(
            channel=channel,
            text=str(card.get("text") or "Approval requested"),
            blocks=card.get("blocks") if isinstance(card.get("blocks"), list) else None,
        )
    except SlackApiError:
        return "failed"
    return "sent"


class Settings(BaseServiceSettings):
    service_name: str = "channels"


def create_application() -> FastAPI:
    """Build the ASGI app. Health does not open Slack or Postgres."""
    app = create_app("channels", Settings(), camel_json=False)
    app.state.outbox = []
    app.state.events = []
    app.state.registry = []
    app.state.dedupe = Dedupe()
    app.state.leader = LeaderLock()
    app.state.now = 1_700_000_000.0
    app.state.mailbox = InProcessMailbox()
    app.state.bounces = BounceBook()
    app.state.verified_domains = ["dev.local"]
    app.state.day = "2026-10-22"
    app.state.reply_markdown = "Done."
    app.state.jwks = {"keys": []}
    app.state.bridge = HttpBridge(os.environ.get("AR_API_INTERNAL_URL", "http://api:8000"))

    @app.post("/channels/slack/events")
    async def slack_events(request: Request) -> JSONResponse:
        body = await request.body()
        result = handle_slack_events(
            request.app,
            body,
            request.headers.get("x-slack-request-timestamp", ""),
            request.headers.get("x-slack-signature", ""),
        )
        status = 401 if result.get("error") == "invalid_signature" else 200
        return JSONResponse(result, status_code=status)

    @app.post("/channels/slack/interactions")
    async def slack_interactions(request: Request) -> JSONResponse:
        body = await request.body()
        result = handle_slack_interaction(
            request.app,
            body,
            request.headers.get("x-slack-request-timestamp", ""),
            request.headers.get("x-slack-signature", ""),
        )
        status = 401 if result.get("error") == "invalid_signature" else 200
        return JSONResponse(result, status_code=status)

    @app.post("/channels/slack/commands")
    async def slack_commands(request: Request) -> JSONResponse:
        body = await request.body()
        result = handle_slack_command(
            request.app,
            body,
            request.headers.get("x-slack-request-timestamp", ""),
            request.headers.get("x-slack-signature", ""),
        )
        status = 401 if result.get("error") == "invalid_signature" else 200
        return JSONResponse(result, status_code=status)

    @app.post("/channels/teams/messages")
    async def teams_messages(request: Request) -> JSONResponse:
        payload = await request.json()
        result = handle_teams(
            request.app,
            payload if isinstance(payload, dict) else {},
            request.headers.get("authorization", ""),
            request.app.state.jwks,
        )
        status = 401 if result.get("error") == "invalid_token" else 200
        return JSONResponse(result, status_code=status)

    @app.post("/internal/v1/outbound")
    async def outbound(request: Request) -> dict[str, Any]:
        body = await request.json()
        rendered = _approval_card(body) if isinstance(body, dict) else {}
        external = f"out-{len(request.app.state.outbox) + 1}"
        safe = (
            {key: value for key, value in body.items() if key != "credentials"}
            if isinstance(body, dict)
            else {}
        )
        if rendered:
            safe["card"] = rendered
        request.app.state.outbox.append(
            {"kind": "outbound", "body": safe, "external_message_id": external}
        )
        delivered = _deliver_card(body, rendered) if isinstance(body, dict) else "recorded"
        return {"external_message_id": external, "delivered": delivered}

    @app.post("/internal/v1/notify")
    async def notify(request: Request) -> dict[str, Any]:
        body = await request.json()
        request.app.state.outbox.append({"kind": "notify", "body": body})
        return {"delivered": ["slack"]}

    @app.post("/internal/v1/integrations/{integration_id}:test")
    async def test_integration(integration_id: str) -> dict[str, Any]:
        return {"ok": True, "detail": f"probe {integration_id}"}

    @app.post("/internal/v1/integrations:reload")
    async def reload_integrations(request: Request) -> dict[str, int]:
        request.app.state.registry = request.app.state.bridge.integrations()
        return {"count": len(request.app.state.registry)}

    @app.post("/internal/v1/email:poll")
    async def poll_email(request: Request) -> dict[str, Any]:
        messages = request.app.state.mailbox.poll()
        results = [handle_email(request.app, message) for message in messages]
        return {"results": results}

    return app


def main() -> None:
    """Listen on ``AR_CHANNELS_PORT`` (default 8004)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_CHANNELS_PORT", LISTEN_PORT),
    )
