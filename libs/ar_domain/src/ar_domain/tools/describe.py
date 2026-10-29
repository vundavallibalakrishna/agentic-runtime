"""Turn a plain-language HTTP description into a tool definition.

The parser is deterministic so a tool can be reviewed without a model call.
Structured fields override anything guessed from the sentence.
"""

from __future__ import annotations

import re

from ar_common.errors import ValidationFailedError
from ar_domain.tools.logic import name_ok, propose_risk

_METHOD = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD)\b", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s)>\]]+")
_CONNECTION = re.compile(r"\bconnection\s+([A-Za-z][A-Za-z0-9_-]{0,40})", re.IGNORECASE)
_PARAM = re.compile(
    r"\b(?:parameter|param|query)\s+([A-Za-z][A-Za-z0-9_-]{0,40})",
    re.IGNORECASE,
)


def compile_description(body: dict[str, object]) -> dict[str, object]:
    """Return a reviewable definition. Nothing is saved."""
    text = str(body.get("description") or "").strip()
    method = str(body.get("method") or "").upper() or _first(_METHOD, text).upper() or "GET"
    if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValidationFailedError("method must be GET, HEAD, POST, PUT, PATCH or DELETE")
    url = str(body.get("url") or "").strip() or _match(_URL, text)
    if not url.startswith(("http://", "https://")):
        raise ValidationFailedError("include the http(s) URL in the description")
    connection = str(body.get("connection") or "").strip() or _first(_CONNECTION, text)
    names = _parameters(body, text)
    title = str(body.get("name") or "").strip() or _title(method, url)
    slug = _slug(str(body.get("slug") or title))
    if not name_ok(slug):
        raise ValidationFailedError("the tool name must be a short lowercase word")
    returns = str(body.get("returns") or "").strip()
    summary = text or f"{method} {url}"
    if returns:
        summary = f"{summary} Returns: {returns}"
    risk = propose_risk("openapi", method=method)
    properties: dict[str, object] = {name: {"type": "string"} for name in names}
    schema: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if method not in {"GET", "HEAD"}:
        properties["body"] = {"type": "object"}
    return {
        "name": slug,
        "title": title[:80],
        "description": summary[:4000],
        "method": method,
        "url": url.split("?")[0],
        "connection": connection,
        "parameters": names,
        "returns": returns,
        "input_schema": schema,
        "risk_class": risk,
        "source": "description",
    }


def _parameters(body: dict[str, object], text: str) -> list[str]:
    raw = body.get("parameters")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return list(dict.fromkeys(_PARAM.findall(text)))


def _first(pattern: re.Pattern[str], text: str) -> str:
    found = pattern.search(text)
    return found.group(1) if found else ""


def _match(pattern: re.Pattern[str], text: str) -> str:
    found = pattern.search(text)
    return found.group(0) if found else ""


def _title(method: str, url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0]
    return f"{method} {host}"[:80]


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")[:48]
    if cleaned and not cleaned[0].isalpha():
        cleaned = f"call_{cleaned}"[:48]
    return cleaned or "call_api"
