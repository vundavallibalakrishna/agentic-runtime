"""Normalise provider payloads and record the replies a fake adapter captures."""

from typing import TYPE_CHECKING

import orjson

from ar_channels.email_channel import accept_email
from ar_channels.render import approval_blocks
from ar_channels.slack import (
    action_value,
    command_text,
    mention_text,
    parse_command,
    render_reply,
    should_ignore,
    signature_ok,
)
from ar_channels.teams import decode_bot_token, welcome_or_message

if TYPE_CHECKING:
    from typing import Any


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _registry(app: Any) -> list[dict[str, Any]]:
    rows = getattr(app.state, "registry", [])
    return [row for row in rows if isinstance(row, dict)]


def slack_integration(app: Any, team_id: str) -> dict[str, Any] | None:
    rows = [row for row in _registry(app) if row.get("kind") == "slack"]
    for row in rows:
        config = row.get("config") if isinstance(row.get("config"), dict) else {}
        if isinstance(config, dict) and str(config.get("team_id") or "") == team_id:
            return row
    if len(rows) == 1:
        return rows[0]
    return None


def _secret(row: dict[str, Any]) -> str:
    credentials = row.get("credentials") if isinstance(row.get("credentials"), dict) else {}
    return str(credentials.get("signing_secret") or "") if isinstance(credentials, dict) else ""


def _record(app: Any, item: dict[str, Any]) -> None:
    app.state.outbox.append(item)


def handle_slack_events(  # noqa: PLR0911
    app: Any, body: bytes, timestamp: str, signature: str
) -> dict[str, Any]:
    payload = orjson.loads(body or b"{}")
    if not isinstance(payload, dict):
        return {"ok": False}
    team = str(payload.get("team_id") or "")
    row = slack_integration(app, team)
    if row is None or not signature_ok(_secret(row), body, timestamp, signature):
        return {"ok": False, "error": "invalid_signature"}
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    event_id = str(payload.get("event_id") or "")
    if event_id and not app.state.dedupe.once(event_id, float(app.state.now)):
        return {"ok": True, "duplicate": True}
    event = _mapping(payload.get("event"))
    config = _mapping(row.get("config"))
    allowed = config.get("allowed_channel_ids") if isinstance(config, dict) else []
    if not isinstance(allowed, list):
        allowed = []
    reason = should_ignore(event, allowed=[str(item) for item in allowed])
    if reason:
        return {"ok": True, "ignored": reason}
    text = mention_text(str(event.get("text") or ""))
    message = {
        "integration_id": row.get("id"),
        "kind": "slack",
        "event_id": event_id,
        "external_user_id": str(event.get("user") or ""),
        "external_channel_id": str(event.get("channel") or ""),
        "external_thread_id": str(event.get("thread_ts") or event.get("ts") or ""),
        "external_message_id": str(event.get("ts") or ""),
        "text": text,
        "mentions_bot": True,
    }
    result = app.state.bridge.inbound(message)
    if result.get("action") == "link_required":
        _record(
            app, {"kind": "slack", "ephemeral": f"Connect your account: {result.get('link_url')}"}
        )
        return {"ok": True, "action": "link_required"}
    if result.get("action") == "unavailable":
        _record(app, {"kind": "slack", "text": "Temporarily unavailable, please retry"})
        return {"ok": True, "action": "unavailable"}
    if result.get("action") == "busy":
        _record(app, {"kind": "slack", "text": "Still working on the previous request"})
        return {"ok": True, "action": "busy"}
    events = list(getattr(app.state, "events", []))
    for part in render_reply(events):
        _record(app, {"kind": "slack", "text": part, "thread": message["external_thread_id"]})
    return {"ok": True, "run_id": result.get("run_id")}


def handle_slack_command(app: Any, body: bytes, timestamp: str, signature: str) -> dict[str, Any]:
    form = parse_command(body)
    row = slack_integration(app, form.get("team_id", ""))
    if row is None or not signature_ok(_secret(row), body, timestamp, signature):
        return {"ok": False, "error": "invalid_signature"}
    slug, text = command_text(form.get("text", ""))
    result = app.state.bridge.inbound(
        {
            "integration_id": row.get("id"),
            "kind": "slack",
            "event_id": form.get("trigger_id", ""),
            "external_user_id": form.get("user_id", ""),
            "external_channel_id": form.get("channel_id", ""),
            "external_thread_id": form.get("trigger_id", ""),
            "text": text,
            "command": {"name": form.get("command", "/agent"), "agent_slug": slug},
        }
    )
    _record(app, {"kind": "slack", "command": True, "result": result.get("action") or "accepted"})
    return {"response_type": "ephemeral", "text": "Working on it."}


def handle_slack_interaction(
    app: Any, body: bytes, timestamp: str, signature: str
) -> dict[str, Any]:
    form = parse_command(body)
    raw = form.get("payload", "")
    payload = orjson.loads(raw or "{}")
    team = ""
    if isinstance(payload, dict) and isinstance(payload.get("team"), dict):
        team = str(payload["team"].get("id") or "")
    row = slack_integration(app, team)
    if row is None or not signature_ok(_secret(row), body, timestamp, signature):
        return {"ok": False, "error": "invalid_signature"}
    actions = payload.get("actions") if isinstance(payload, dict) else []
    if not isinstance(actions, list) or not actions:
        return {"ok": True}
    value = action_value(str(actions[0].get("value") or ""))
    decided = app.state.bridge.approval(
        {
            "approval_id": value.get("approval_id", ""),
            "decision": value.get("decision", ""),
            "args_hash": value.get("args_hash", ""),
            "integration_id": row.get("id"),
        }
    )
    _record(app, {"kind": "slack", "approval": decided})
    return {"ok": True, "result": decided.get("result")}


def slack_approval_message(approval_id: str, args_hash: str, *, step_up: bool) -> dict[str, object]:
    return {
        "text": "Approval requested",
        "blocks": approval_blocks(approval_id, args_hash, step_up=step_up, web_url="/approvals"),
    }


def handle_teams(
    app: Any, body: dict[str, Any], authorization: str, jwks: dict[str, Any]
) -> dict[str, Any]:
    rows = [row for row in _registry(app) if row.get("kind") == "teams"]
    row = rows[0] if rows else None
    if row is None:
        return {"ok": False}
    credentials = row.get("credentials") if isinstance(row.get("credentials"), dict) else {}
    audience = str(credentials.get("app_id") or "") if isinstance(credentials, dict) else ""
    token = authorization.removeprefix("Bearer ").strip()
    try:
        decode_bot_token(token, jwks, audience)
    except Exception:  # noqa: BLE001 — a bad bot token is a 401 at the edge
        return {"ok": False, "error": "invalid_token"}
    parsed = welcome_or_message(body)
    if parsed.get("action") == "welcome":
        _record(app, {"kind": "teams", "text": parsed.get("text")})
        return {"ok": True, "action": "welcome"}
    if parsed.get("action") != "message":
        if parsed.get("action") == "invoke":
            _record(app, {"kind": "teams", "card": parsed.get("card")})
        return {"ok": True, "action": parsed.get("action")}
    result = app.state.bridge.inbound(
        {
            "integration_id": row.get("id"),
            "kind": "teams",
            "external_user_id": parsed.get("external_user_id"),
            "external_channel_id": parsed.get("external_channel_id"),
            "external_thread_id": parsed.get("external_channel_id"),
            "text": parsed.get("text"),
            "mentions_bot": True,
        }
    )
    _record(app, {"kind": "teams", "card": parsed.get("card"), "result": result})
    return {"ok": True, "run_id": result.get("run_id")}


def handle_email(app: Any, message: dict[str, str]) -> dict[str, str]:
    decision = accept_email(
        message,
        domains=set(getattr(app.state, "verified_domains", [])),
        bounces=app.state.bounces,
        day=str(getattr(app.state, "day", "1970-01-01")),
    )
    if decision["action"] == "bounce":
        app.state.mailbox.send({"to": decision["to"], "body": decision["body"]})
        return decision
    if decision["action"] != "accept":
        return decision
    rows = [row for row in _registry(app) if row.get("kind") == "email"]
    row = rows[0] if rows else None
    if row is None:
        return {"action": "drop"}
    result = app.state.bridge.inbound(
        {
            "integration_id": row.get("id"),
            "kind": "email",
            "external_user_id": message.get("from", ""),
            "external_user_email": message.get("from", ""),
            "external_channel_id": message.get("to", ""),
            "external_thread_id": message.get("message_id", ""),
            "external_message_id": message.get("message_id", ""),
            "text": message.get("body", ""),
        }
    )
    if result.get("action") is None:
        from ar_channels.render import render_email_html, reply_headers  # noqa: PLC0415

        headers = reply_headers(message.get("message_id", ""), message.get("references", ""))
        app.state.mailbox.send(
            {
                "to": message.get("from", ""),
                "body": render_email_html(str(getattr(app.state, "reply_markdown", "Done."))),
                "in_reply_to": headers["In-Reply-To"],
                "references": headers["References"],
            }
        )
    return {"action": "accepted"}
