"""Teams activities and Bot Framework JWTs."""

from typing import TYPE_CHECKING

import jwt
from microsoft_agents.activity import Activity

from ar_channels.render import adaptive_card

if TYPE_CHECKING:
    from typing import Any


def decode_bot_token(token: str, jwks: dict[str, Any], audience: str) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise jwt.InvalidTokenError("missing jwks")
    kid = str(header.get("kid") or "")
    chosen = next(
        (item for item in keys if isinstance(item, dict) and item.get("kid") == kid), keys[0]
    )
    if not isinstance(chosen, dict):
        raise jwt.InvalidTokenError("missing jwk")
    claims = jwt.decode(
        token,
        jwt.PyJWK.from_dict(chosen).key,
        algorithms=["RS256"],
        audience=audience,
        issuer="https://api.botframework.com",
    )
    if not isinstance(claims, dict):
        raise jwt.InvalidTokenError("claims")
    return claims


def read_activity(body: dict[str, Any]) -> Activity:
    return Activity.model_validate(body)


def activity_message(body: dict[str, Any]) -> dict[str, str]:
    activity = read_activity(body)
    sender = activity.from_property
    conversation = activity.conversation
    text = str(activity.text or "")
    mentioned = "mention" in text.lower() or "<at>" in text.lower()
    return {
        "type": str(activity.type or ""),
        "text": text.replace("<at>", "").replace("</at>", "").strip(),
        "external_user_id": "" if sender is None else str(sender.id or ""),
        "external_channel_id": "" if conversation is None else str(conversation.id or ""),
        "mentioned": "yes" if mentioned else "",
    }


def welcome_or_message(body: dict[str, Any]) -> dict[str, object]:
    parsed = activity_message(body)
    if parsed["type"] == "conversationUpdate":
        return {
            "action": "welcome",
            "text": "Hello. Mention me in a channel or send a direct message.",
        }
    if parsed["type"] == "message":
        return {"action": "message", **parsed, "card": adaptive_card(parsed["text"] or "…")}
    if parsed["type"] == "invoke":
        return {"action": "invoke", **parsed}
    return {"action": "ignore"}
