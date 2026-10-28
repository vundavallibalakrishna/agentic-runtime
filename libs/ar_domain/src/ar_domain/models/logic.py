"""Alias resolution, SSRF checks and parameter merge. Spec: docs/03-specs/04-model-gateway.md."""

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import orjson

_ALIAS = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")
_STRIPPED = frozenset({"model", "stream", "messages", "tools", "tool_choice"})
DEFAULT_DENY_CIDRS = (
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
)


@dataclass(frozen=True, slots=True)
class AliasRef:
    """One alias row the resolver can see."""

    tenant_id: str | None
    alias: str
    kind: str
    primary_model_id: str
    fallback_model_ids: tuple[str, ...]
    status: str
    default_params: dict[str, object]


def valid_alias(name: str) -> bool:
    """Return whether ``name`` matches the catalogue pattern."""
    return _ALIAS.fullmatch(name) is not None


def resolve_alias(rows: list[AliasRef], tenant_id: str, name: str) -> AliasRef | None:
    """Tenant alias wins over the platform alias with the same name."""
    active = [row for row in rows if row.alias == name and row.status == "active"]
    tenant = next((row for row in active if row.tenant_id == tenant_id), None)
    if tenant is not None:
        return tenant
    return next((row for row in active if row.tenant_id is None), None)


def merge_params(defaults: dict[str, object], requested: dict[str, object]) -> dict[str, object]:
    """Alias defaults, then caller params. Identity fields are stripped."""
    merged = {**defaults, **requested}
    return {key: value for key, value in merged.items() if key not in _STRIPPED}


def _parse_host(url: str) -> str:
    host = urlparse(url).hostname
    return "" if host is None else host


def provider_url_denied(
    url: str, deny_cidrs: tuple[str, ...] | list[str], *, allow_loopback: bool
) -> bool:
    """Reject provider URLs whose host is inside the deny list.

    Loopback and the ``fake-llm`` hostname are allowed only when
    ``allow_loopback`` is set (dev and CI). Non-IP hostnames other than
    ``localhost`` are not denied here; DNS rebinding is rejected at request time
    by the same check after resolution.
    """
    host = _parse_host(url)
    if host == "":
        return True
    if host == "fake-llm":
        return not allow_loopback
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost":
            return not allow_loopback
        return False
    if allow_loopback and address.is_loopback:
        return False
    return any(address in ipaddress.ip_network(cidr, strict=False) for cidr in deny_cidrs)


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Drop a reasoning model's private trace and keep the answer."""
    stripped = _THINK.sub("", text).strip()
    return stripped or text.strip()


_TOOL_BLOCK = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def completion_tool_calls(payload: object) -> list[dict[str, object]]:
    """OpenAI tool_calls, or a Qwen ``<tool_call>`` JSON block in the message."""
    message = _message(payload)
    if message is None:
        return []
    found: list[dict[str, object]] = []
    raw = message.get("tool_calls")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "")
            if name:
                found.append({"name": name, "arguments": _arguments(function.get("arguments"))})
    if found:
        return found
    content = message.get("content")
    text = content if isinstance(content, str) else ""
    for match in _TOOL_BLOCK.finditer(text):
        try:
            parsed = orjson.loads(match.group(1))
        except orjson.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        name = str(parsed.get("name") or "")
        if name:
            found.append({"name": name, "arguments": _arguments(parsed.get("arguments"))})
    return found


def visible_answer(text: str) -> str:
    """Drop a tool-call block so it is not shown as the assistant's reply."""
    return _TOOL_BLOCK.sub("", text).strip()


def _message(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    if isinstance(message, dict):
        return message
    return None


def _arguments(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = orjson.loads(value)
        except orjson.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def completion_text(payload: object) -> str:
    """Read assistant text, including a reasoning field when content is empty."""
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    text = content if isinstance(content, str) else ""
    if not text.strip():
        reasoning = message.get("reasoning_content")
        text = reasoning if isinstance(reasoning, str) else ""
    return strip_think(text)
