"""Slack signature, events, commands and interactions."""

from urllib.parse import parse_qs

import orjson
from slack_bolt import App
from slack_sdk.signature import SignatureVerifier

from ar_channels.render import split_message, throttled_snapshots, to_mrkdwn


def verifier(secret: str) -> SignatureVerifier:
    return SignatureVerifier(secret)


def signature_ok(secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    return bool(verifier(secret).is_valid(body.decode(), timestamp, signature))


def bolt_app(bot_token: str) -> App:
    """Socket Mode app. The leader holds one of these per integration."""
    return App(
        token=bot_token,
        signing_secret="socket",  # noqa: S106
        token_verification_enabled=False,
    )


def parse_command(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode())
    return {key: values[0] for key, values in parsed.items() if values}


def command_text(text: str) -> tuple[str, str]:
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    first = parts[0]
    if first.startswith("/") or (
        " " in text.strip() and first.replace("-", "").isalnum() and first.islower()
    ):
        rest = parts[1] if len(parts) > 1 else ""
        if not first.startswith("/"):
            return first, rest
    return "", text.strip()


def mention_text(text: str) -> str:
    stripped = text
    while stripped.startswith("<@"):
        end = stripped.find(">")
        if end < 0:
            break
        stripped = stripped[end + 1 :].strip()
    return stripped


def should_ignore(event: dict[str, object], *, allowed: list[str]) -> str:
    if event.get("bot_id") or event.get("subtype") in {"message_changed", "message_deleted"}:
        return "ignore"
    channel = str(event.get("channel") or "")
    channel_type = str(event.get("channel_type") or "")
    if allowed and channel_type != "im" and channel not in allowed:
        return "channel_not_allowed"
    kind = str(event.get("type") or "")
    if kind == "app_mention" or channel_type == "im" or event.get("thread_ts"):
        return ""
    return "ignore"


def render_reply(events: list[dict[str, object]]) -> list[str]:
    shots = throttled_snapshots(events, 1500)
    rendered: list[str] = []
    for shot in shots:
        rendered.extend(split_message(to_mrkdwn(shot)))
    return rendered


def action_value(raw: str) -> dict[str, str]:
    if raw.startswith("{"):
        loaded = orjson.loads(raw)
        if isinstance(loaded, dict):
            return {str(key): str(value) for key, value in loaded.items()}
    parts = raw.split("|")
    if len(parts) >= 3:
        return {"approval_id": parts[0], "args_hash": parts[1], "decision": parts[2]}
    return {}
