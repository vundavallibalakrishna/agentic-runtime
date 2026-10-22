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
)
from ar_channels.state import Dedupe, LeaderLock
from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

if TYPE_CHECKING:
    from typing import Any

LISTEN_PORT = 8004


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
        external = f"out-{len(request.app.state.outbox) + 1}"
        request.app.state.outbox.append(
            {"kind": "outbound", "body": body, "external_message_id": external}
        )
        return {"external_message_id": external}

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
