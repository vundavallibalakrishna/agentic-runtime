"""Host-signed widget JWTs. Spec: docs/03-specs/16-channels.md §7."""

import base64
import hashlib
import hmac
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
import orjson
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ar_common.errors import ForbiddenError
from ar_common.http import http_client
from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def allowed_origins(config: object) -> list[str]:
    """Only exact HTTP(S) origins may appear in frame-ancestors or postMessage."""
    if not isinstance(config, dict):
        return []
    raw = config.get("allowed_origins", config.get("allowedOrigins", []))
    if not isinstance(raw, list):
        return []
    found = []
    for value in raw:
        if not isinstance(value, str) or any(c.isspace() for c in value):
            continue
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError:
            continue
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in value
            or ";" in value
            or "\\" in value
            or parsed.scheme not in {"https", "http"}
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
            or (port is not None and not 0 < port <= 65535)
        ):
            continue
        found.append(value)
    return list(dict.fromkeys(found))


_SESSION_DEFAULT_S = 1800
_SESSION_MAX_S = 86_400
_MESSAGES_DEFAULT = 30
_SESSIONS_PER_MINUTE_DEFAULT = 60
_SESSIONS_PER_CLIENT_DEFAULT = 10
_NOTICE_MAX = 2000
_MESSAGE_CHARS_DEFAULT = 2000


def public_access(config: object) -> dict[str, Any] | None:
    """A public widget's settings, or None for one whose host signs its visitors in.

    A public widget is for a website anyone may visit. Nobody is signed in, so every
    visitor acts as one account the tenant names (``visitorEmail``), with only the right
    to chat, to the agents the integration lists. Each visitor has a session of their
    own and reaches only the conversation made in it. The settings bound what a visitor,
    or a script posing as many, can use.
    """
    if not isinstance(config, dict) or str(config.get("access") or "") != "public":
        return None

    def number(names: tuple[str, str], default: int, most: int) -> int:
        raw = config.get(names[0], config.get(names[1]))
        value = raw if isinstance(raw, int) and not isinstance(raw, bool) else default
        return max(1, min(value, most))

    return {
        "visitor_email": str(config.get("visitorEmail") or config.get("visitor_email") or "")
        .strip()
        .lower(),
        "session_s": number(
            ("sessionSeconds", "session_seconds"), _SESSION_DEFAULT_S, _SESSION_MAX_S
        ),
        "max_messages": number(("maxMessages", "max_messages"), _MESSAGES_DEFAULT, 1000),
        "sessions_per_minute": number(
            ("sessionsPerMinute", "sessions_per_minute"), _SESSIONS_PER_MINUTE_DEFAULT, 6000
        ),
        "sessions_per_client": number(
            ("sessionsPerClientPerMinute", "sessions_per_client_per_minute"),
            _SESSIONS_PER_CLIENT_DEFAULT,
            600,
        ),
        "notice": str(config.get("notice") or "")[:_NOTICE_MAX],
        "max_message_chars": number(
            ("maxMessageChars", "max_message_chars"), _MESSAGE_CHARS_DEFAULT, 32000
        ),
    }


def show_sources(config: object) -> bool:
    """Whether the widget shows the sources an answer cites. On unless turned off.

    A tenant whose agent answers from documents it does not want named to visitors turns
    it off (``showSources: false``); the widget then receives no citation at all.
    """
    if not isinstance(config, dict):
        return True
    raw = config.get("showSources", config.get("show_sources"))
    return raw is not False


def without_sources(conversation: dict[str, Any]) -> dict[str, Any]:
    """A conversation with every cited source taken out of its messages."""
    messages = conversation.get("messages")
    if not isinstance(messages, list):
        return conversation

    def bare(message: object) -> object:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(message, dict) or not isinstance(content, list):
            return message
        return {
            **message,
            "content": [
                part
                for part in content
                if not (isinstance(part, dict) and part.get("type") == "citation_ref")
            ],
        }

    return {**conversation, "messages": [bare(message) for message in messages]}


def allows_visitors(definition: object) -> bool:
    """Whether an agent's published definition lets people who are not signed in chat."""
    channels = definition.get("channels") if isinstance(definition, dict) else None
    return isinstance(channels, dict) and channels.get("public") is True


def client_address(peer: str, forwarded: str, trusted: str) -> str:
    """The address a request is counted against.

    ``peer`` is who connected. When that is one of the install's own proxies, the visitor
    is the last address in ``X-Forwarded-For`` that is not such a proxy. A caller that is
    not a trusted proxy is counted as itself: what it writes in the header is not believed,
    or one script could pose as any number of visitors.
    """
    import ipaddress  # noqa: PLC0415

    networks = []
    for item in trusted.split(","):
        try:
            networks.append(ipaddress.ip_network(item.strip(), strict=False))
        except ValueError:
            continue

    def ours(value: str) -> bool:
        try:
            address = ipaddress.ip_address(value.strip())
        except ValueError:
            return False
        return any(address in network for network in networks)

    if not ours(peer):
        return peer
    for hop in reversed([part.strip() for part in forwarded.split(",") if part.strip()]):
        if not ours(hop):
            try:
                return str(ipaddress.ip_address(hop))
            except ValueError:
                return peer
    return peer


def _claims(  # noqa: PLR0911 - each malformed claim fails closed
    token: str, audience: str, algorithm: str
) -> tuple[dict[str, Any], bytes, bytes] | None:
    parts = token.split(".")
    if len(parts) != 3 or len(token) > 16384:
        return None
    try:
        header = orjson.loads(_b64(parts[0]))
        payload = orjson.loads(_b64(parts[1]))
        signature = _b64(parts[2])
    except ValueError:
        return None
    if not isinstance(header, dict) or header.get("alg") != algorithm or header.get("crit"):
        return None
    if not isinstance(payload, dict) or payload.get("aud") != audience:
        return None
    now = int(utcnow().timestamp())
    exp = payload.get("exp")
    if type(exp) is not int or not now < exp <= now + 600:
        return None
    if not isinstance(payload.get("sub"), str) or not payload["sub"].strip():
        return None
    for field in ("nbf", "iat"):
        value = payload.get(field)
        if value is not None and (type(value) is not int or value > now):
            return None
    return payload, f"{parts[0]}.{parts[1]}".encode(), signature


def verify_widget_token(token: str, secret: str, audience: str) -> dict[str, Any] | None:
    """Validate HS256, the integration audience and a maximum ten-minute lifetime."""
    parsed = _claims(token, audience, "HS256")
    if not secret or parsed is None:
        return None
    payload, signing, signature = parsed
    expected = hmac.new(secret.encode(), signing, hashlib.sha256).digest()
    return payload if hmac.compare_digest(expected, signature) else None


def verify_rsa_widget_token(token: str, jwks: object, audience: str) -> dict[str, Any] | None:
    """Accept only the registered RSA signing key, never a key supplied in the token."""
    parsed = _claims(token, audience, "RS256")
    if parsed is None or not isinstance(jwks, dict):
        return None
    header = orjson.loads(_b64(token.split(".", maxsplit=1)[0]))
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not isinstance(header.get("kid"), str):
        return None
    for key in keys:
        if not isinstance(key, dict) or key.get("kid") != header["kid"] or key.get("kty") != "RSA":
            continue
        if key.get("use", "sig") != "sig" or key.get("alg", "RS256") != "RS256":
            continue
        try:
            public = rsa.RSAPublicNumbers(
                int.from_bytes(_b64(str(key["e"]))), int.from_bytes(_b64(str(key["n"])))
            ).public_key()
            if public.key_size < 2048:
                return None
            public.verify(parsed[2], parsed[1], padding.PKCS1v15(), hashes.SHA256())
        except KeyError, ValueError, InvalidSignature:
            return None
        return parsed[0]
    return None


async def verify_registered_token(
    token: str, *, secret: str, audience: str, config: dict[str, object]
) -> dict[str, Any] | None:
    """Fetch only the administrator-registered HTTPS JWKS, with SSRF protection."""
    url = config.get("jwks_url", config.get("jwksUrl"))
    if not url:
        return verify_widget_token(token, secret, audience)
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    client = http_client()
    try:
        response = await client.request("GET", url, timeout=5)
        if response.status_code != 200 or len(response.content) > 65536:
            return None
        return verify_rsa_widget_token(token, response.json(), audience)
    except httpx.HTTPError, ForbiddenError, ValueError:
        return None
    finally:
        await client.aclose()


def sign_widget_token(*, secret: str, audience: str, email: str, name: str, exp: int) -> str:
    """Test and host helper. The product does not mint widget tokens."""
    header = _b64encode(orjson.dumps({"alg": "HS256", "typ": "JWT"}))
    body = _b64encode(orjson.dumps({"sub": email, "name": name, "aud": audience, "exp": exp}))
    signing = f"{header}.{body}".encode()
    signature = _b64encode(hmac.new(secret.encode(), signing, hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def _b64(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
