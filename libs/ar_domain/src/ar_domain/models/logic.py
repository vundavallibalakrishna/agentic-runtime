"""Alias resolution, SSRF checks and parameter merge. Spec: docs/03-specs/04-model-gateway.md."""

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

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


def provider_url_denied(  # noqa: PLR0911
    url: str, deny_cidrs: tuple[str, ...] | list[str], *, allow_loopback: bool
) -> bool:
    """Reject provider URLs whose host is inside the deny list.

    Loopback, ``localhost``, ``fake-llm`` and decimal or octal spellings of a
    loopback address are allowed only when ``allow_loopback`` is set. A mapped
    or decimal metadata address is denied. Other hostnames are checked again
    when the call is placed.
    """
    from ar_common.egress_policy import (  # noqa: PLC0415
        canonical_ip,
        is_operator_private,
        metadata_address,
        named_private_allowed,
    )

    host = _parse_host(url)
    if host == "":
        return True
    if metadata_address(host):
        return True
    if host in {"fake-llm", "localhost"}:
        return not allow_loopback
    address = canonical_ip(host)
    if address is None:
        return False
    if address.is_loopback:
        return not allow_loopback
    if named_private_allowed() and is_operator_private(str(address)):
        return False
    return any(address in ipaddress.ip_network(cidr, strict=False) for cidr in deny_cidrs)


_THINK_PAIR = re.compile(r"<think\b[^>]*>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</think>", re.IGNORECASE)


def split_thinking(text: str) -> tuple[str, str]:
    """Visible answer and the private trace.

    Closed ``<think>`` blocks, an unclosed opening tag, and a leading
    ``</think>`` (the chat template already opened the tag) all count. The
    trace is not put back into the answer when it was the whole reply.
    """
    if not text:
        return "", ""
    reasoning: list[str] = []

    def _keep(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if inner:
            reasoning.append(inner)
        return ""

    visible = _THINK_PAIR.sub(_keep, text)
    opened = _THINK_OPEN.search(visible)
    if opened is not None:
        inner = visible[opened.end() :].strip()
        if inner:
            reasoning.append(inner)
        visible = visible[: opened.start()]
    else:
        closed = _THINK_CLOSE.search(visible)
        if closed is not None:
            inner = visible[: closed.start()].strip()
            if inner:
                reasoning.append(inner)
            visible = visible[closed.end() :]
    return visible.strip(), "\n".join(reasoning)


def strip_think(text: str) -> str:
    """Drop a reasoning model's private trace and keep the answer."""
    return split_thinking(text)[0]


def think_trace(text: str) -> str:
    """The private trace inside ``<think>`` tags, without the tags."""
    return split_thinking(text)[1]


def resolved_model_label(upstream_model: str) -> str:
    """The model a person should see, taken from the resolved upstream id.

    ``Qwen/Qwen3-32B`` is shown as ``Qwen3-32B``. An id with no slash is already
    that label.
    """
    name = upstream_model.strip()
    if "/" in name:
        return name.rsplit("/", 1)[-1]
    return name


def completion_message(payload: object, *, strip_thinking: bool = True) -> dict[str, object]:
    """Assistant text, tool calls and token counts from one chat completion."""
    text = completion_text(payload, strip_thinking=strip_thinking)
    calls: list[dict[str, object]] = []
    usage = _usage(payload if isinstance(payload, dict) else None)
    if not isinstance(payload, dict):
        return {"text": text, "tool_calls": calls, "usage": usage}
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {"text": text, "tool_calls": calls, "usage": usage}
    message = choices[0].get("message")
    reasoning = ""
    if isinstance(message, dict):
        raw_calls = message.get("tool_calls")
        if isinstance(raw_calls, list):
            seen: set[str] = set()
            for index, call in enumerate(raw_calls):
                parsed = _tool_call(index, call)
                if parsed is None:
                    continue
                # A provider that repeats an id would store two rows under one key.
                ident = str(parsed["id"])
                if ident in seen:
                    parsed["id"] = f"{ident}:{index}"
                seen.add(str(parsed["id"]))
                calls.append(parsed)
        reasoning = _reasoning_trace(message, strip_thinking=strip_thinking, answer=text)
    return {"text": text, "tool_calls": calls, "usage": usage, "reasoning": reasoning}


def _usage(payload: dict[str, object] | None) -> dict[str, object]:
    """Provider counts when the payload has them. Omitted usage is not a zero report."""
    raw = payload.get("usage") if isinstance(payload, dict) else None
    if isinstance(raw, dict) and _reported(raw):
        return {
            "tokens_in": _whole(raw.get("prompt_tokens")),
            "tokens_out": _whole(raw.get("completion_tokens")),
            "usage_source": "provider",
        }
    return {"tokens_in": 0, "tokens_out": 0, "usage_source": "unknown"}


def _reported(raw: dict[str, object]) -> bool:
    return "prompt_tokens" in raw or "completion_tokens" in raw


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _reasoning_trace(message: dict[str, object], *, strip_thinking: bool, answer: str) -> str:
    """A separate thinking trace. Text that became the answer is not repeated here."""
    if not strip_thinking:
        return ""
    content = message.get("content")
    chunks: list[str] = []
    if isinstance(content, str):
        found = think_trace(content)
        if found and found != answer:
            chunks.append(found)
    raw = message.get("reasoning_content")
    if isinstance(raw, str) and raw.strip() and raw.strip() != answer:
        trace = think_trace(raw) or raw.strip()
        if trace and trace != answer:
            chunks.append(trace)
    return "\n".join(chunks)


def _tool_call(index: int, call: object) -> dict[str, object] | None:
    if not isinstance(call, dict):
        return None
    function = call.get("function")
    if not isinstance(function, dict):
        return None
    from ar_domain.models.arguments import parse_tool_arguments  # noqa: PLC0415

    parsed = parse_tool_arguments(function.get("arguments"))
    ident = call.get("id")
    row: dict[str, object] = {
        "id": str(ident).strip() if isinstance(ident, str) and ident.strip() else f"call_{index}",
        "name": str(function.get("name") or ""),
        "arguments": parsed.arguments if parsed.ok else {},
        "arguments_raw": parsed.raw,
    }
    if not parsed.ok:
        row["arguments_error"] = parsed.error
    elif parsed.repaired:
        row["arguments_repaired"] = True
    return row


def completion_text(payload: object, *, strip_thinking: bool = True) -> str:
    """Read assistant text. A reasoning field is the answer only when content is empty."""
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
    if not strip_thinking:
        return text.strip()
    return strip_think(text)
