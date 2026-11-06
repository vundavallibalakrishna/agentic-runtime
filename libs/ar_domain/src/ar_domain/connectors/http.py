"""Shared HTTP calls: auth, pagination, rate limits and errors a person can act on."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import orjson

from ar_common.offload import blocking
from ar_domain.tools.http_tools import guard_public

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ar_domain.connectors.catalog import ConnectorDef, ToolDef

_LIST_KEYS = (
    "items",
    "values",
    "value",
    "issues",
    "files",
    "results",
    "messages",
    "comments",
    "channels",
    "records",
    "result",
    "projects",
)
_PAGE_CAP = 3
_ITEM_CAP = 50
_TEXT_CAP = 4000


def explain_status(status: int, headers: Mapping[str, str]) -> str:
    """Say what to do about a provider status. The body is not included."""
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    if status == 401:
        return (
            "The provider rejected the credential (401). "
            "Reconnect the account on the connector page and try again."
        )
    if status == 403:
        if lowered.get("x-ratelimit-remaining") == "0":
            return "The provider is rate limiting requests (403). Wait and try again."
        return (
            "The account does not have permission for this action (403). "
            "Check the scopes in the setup guide."
        )
    if status == 404:
        return "The provider could not find that item (404)."
    if status == 429:
        retry = lowered.get("retry-after") or "a short while"
        return f"The provider is rate limiting requests (429). Retry after {retry}."
    return f"The provider returned HTTP {status}."


def slack_error(code: str) -> str:
    if code in {"invalid_auth", "not_authed", "token_revoked", "account_inactive"}:
        return explain_status(401, {})
    if code in {"missing_scope", "not_allowed", "restricted_action"}:
        return explain_status(403, {})
    if code == "ratelimited":
        return explain_status(429, {})
    if code in {"channel_not_found", "message_not_found"}:
        return explain_status(404, {})
    return f"Slack returned {code}. Check the channel, the scopes and the token."


def rate_limited(store: Any, tenant: object, slug: str, per_minute: int) -> str | None:
    shared = _shared_limit(store, tenant, slug, per_minute)
    if shared is not _SKIP:
        return shared if isinstance(shared, str) else None
    book = getattr(store, "rate_buckets", None)
    if not isinstance(book, dict):
        store.rate_buckets = {}
        book = store.rate_buckets
    import time  # noqa: PLC0415

    now = time.time()
    key = f"connector:{tenant}:{slug}"
    current = book.get(key)
    stamps = (
        [item for item in current if isinstance(item, float)] if isinstance(current, list) else []
    )
    fresh = [item for item in stamps if item >= now - 60]
    if len(fresh) >= per_minute:
        return (
            f"{slug} is at its local limit of {per_minute} calls a minute. "
            "Wait a minute and try again."
        )
    fresh.append(now)
    book[key] = fresh
    return None


_SKIP = object()


def _shared_limit(store: Any, tenant: object, slug: str, per_minute: int) -> object:
    """Count on Valkey so workers share one bucket. ``_SKIP`` means use memory."""
    client = getattr(store, "valkey_client", None)
    if client is None:
        return _SKIP
    import time  # noqa: PLC0415

    minute = int(time.time() // 60)
    key = f"ar:connector-rate:{tenant}:{slug}:{minute}"
    try:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 70)
    except Exception:  # noqa: BLE001 — Valkey loss keeps the process-local bucket
        return _SKIP
    if count > per_minute:
        return (
            f"{slug} is at its shared limit of {per_minute} calls a minute. "
            "Wait a minute and try again."
        )
    return None


def run_http(  # noqa: PLR0911, PLR0912, PLR0915, PLR0917
    store: Any,
    connector: ConnectorDef,
    tool: ToolDef,
    arguments: dict[str, object],
    headers: dict[str, str],
    base_url: str,
) -> dict[str, object]:
    """Call one REST operation and follow its pagination."""
    from ar_domain.connectors.shape import request_body, request_path  # noqa: PLC0415

    try:
        path = request_path(tool, arguments)
    except KeyError as exc:
        return _fail("validation_failed", f"{exc.args[0]} is required")
    missing = [name for name in tool.required if not _present(arguments.get(name))]
    if missing:
        return _fail("validation_failed", f"{missing[0]} is required")
    url = _join(base_url, path)
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        return _fail("egress_denied", problem)
    params = {
        key: arguments[key]
        for key in tool.query
        if _present(arguments.get(key)) and key not in path
    }
    if tool.name == "gdrive_download":
        params.setdefault("alt", "media")
    if tool.name == "confluence_read_page":
        params.setdefault("expand", "body.storage")
    body = request_body(connector, tool, arguments)
    method = (
        "PUT" if tool.name == "confluence_write_page" and arguments.get("page_id") else tool.method
    )
    if tool.name == "confluence_write_page" and arguments.get("page_id"):
        url = _join(base_url, f"/wiki/rest/api/content/{arguments['page_id']}")
    pages = 0
    items: list[object] = []
    last: object = {}
    while pages < _PAGE_CAP and url:
        status, payload, response_headers, error = _once(
            store, connector, method, url, headers, params, body
        )
        if error:
            return error
        if status >= 400:
            return _fail("upstream_error", explain_status(status, response_headers))
        if isinstance(payload, dict) and payload.get("ok") is False:
            return _fail("upstream_error", slack_error(str(payload.get("error") or "error")))
        last = payload
        found = _extract(payload)
        if found is None:
            break
        items.extend(found)
        pages += 1
        if len(items) >= _ITEM_CAP or tool.page == "none":
            break
        if tool.page == "after":
            token = _after_token(payload)
            if not token:
                break
            if method == "GET":
                url = _with_query(url, "after", token)
                params = {}
            else:
                body = dict(body or {})
                body["after"] = token
            continue
        page_url = url
        if tool.page == "servicenow":
            for key, value in params.items():
                page_url = _with_query(page_url, key, value)
        nxt = _next(tool.page, payload, response_headers, page_url)
        if not nxt or nxt == url:
            break
        problem = guard_public(nxt, allow=["*"], loopback=True)
        if problem:
            return _fail("egress_denied", problem)
        url = nxt
        params = {}
        body = None
        method = "GET"
    if items:
        trimmed = items[:_ITEM_CAP]
        payload_out: object = {"items": trimmed, "pages": pages}
        if tool.name == "github_read_file":
            payload_out = _github_file(last)
        return _ok(_text(payload_out), payload_out if isinstance(payload_out, dict) else {})
    shown = _github_file(last) if tool.name == "github_read_file" else last
    structured = shown if isinstance(shown, dict) else {"value": shown}
    return _ok(_text(shown), structured)


def probe_http(
    store: Any,
    connector: ConnectorDef,
    headers: dict[str, str],
    base_url: str,
    path: str | None = None,
) -> dict[str, object]:
    url = _join(base_url, connector.probe_path if path is None else path)
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        return {"ok": False, "status": 0, "error": problem}
    status, _payload, response_headers, error = _once(
        store, connector, connector.probe_method or "GET", url, headers, {}, None
    )
    if error:
        return {
            "ok": False,
            "status": 0,
            "error": str(error.get("text") or "the host did not answer"),
        }
    if status == 401:
        return {"ok": False, "status": status, "error": explain_status(status, response_headers)}
    if status >= 400:
        return {"ok": False, "status": status, "error": explain_status(status, response_headers)}
    return {"ok": True, "status": status, "error": None}


def _once(  # noqa: PLR0917
    store: Any,
    connector: ConnectorDef,
    method: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, object],
    body: dict[str, object] | None,
) -> tuple[int, object, dict[str, str], dict[str, object] | None]:
    request_headers = _provider_headers(connector, headers)
    transport = getattr(store, "connector_transport", None)
    kwargs: dict[str, object] = {"timeout": 20.0, "follow_redirects": False}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as client:  # type: ignore[arg-type]
            request_kwargs: dict[str, object] = {"headers": request_headers}
            if params:
                request_kwargs["params"] = {key: str(value) for key, value in params.items()}
            if body is not None:
                request_kwargs["json"] = body
            response = blocking(client.request, method, url, **request_kwargs)
    except httpx.HTTPError:
        return (
            0,
            {},
            {},
            _fail("upstream_error", "The provider did not answer. Check the host and try again."),
        )
    if response.status_code in {301, 302, 303, 307, 308}:
        return (
            response.status_code,
            {},
            {},
            _fail(
                "upstream_error",
                "The provider redirected the request. The connector does not follow redirects.",
            ),
        )
    payload = _payload(response)
    return (
        response.status_code,
        payload,
        dict(response.headers.items()),
        None,
    )


def _provider_headers(connector: ConnectorDef, headers: dict[str, str]) -> dict[str, str]:
    merged = {"Accept": "application/json", "User-Agent": "agentic-runtime-connector", **headers}
    if connector.slug == "github":
        merged["Accept"] = "application/vnd.github+json"
        merged["X-GitHub-Api-Version"] = "2022-11-28"
    if connector.slug == "notion":
        merged["Notion-Version"] = "2022-06-28"
    if connector.slug == "okta":
        auth = merged.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            merged["Authorization"] = "SSWS " + auth.split(" ", 1)[1]
    return merged


def _payload(response: httpx.Response) -> object:
    content_type = response.headers.get("content-type", "")
    raw = response.content[:1_000_000]
    if "json" in content_type or raw[:1] in {b"{", b"["}:
        try:
            return orjson.loads(raw)
        except orjson.JSONDecodeError:
            return {"text": raw[:_TEXT_CAP].decode("utf-8", errors="replace")}
    text = raw[:_TEXT_CAP].decode("utf-8", errors="replace")
    return {"text": text, "contentType": content_type}


def _join(base: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base.rstrip("/") + "/" + path.lstrip("/")


def _present(value: object) -> bool:
    return value is not None and str(value) != ""


def _extract(payload: object) -> list[object] | None:
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        messages = payload.get("messages")
        if isinstance(messages, dict) and isinstance(messages.get("matches"), list):
            return list(messages["matches"])
        for key in _LIST_KEYS:
            found = payload.get(key)
            if isinstance(found, list):
                return list(found)
    return None


def _next(  # noqa: PLR0911
    mode: str, payload: object, headers: Mapping[str, str], url: str
) -> str:
    if mode == "link":
        return _link(headers.get("link") or headers.get("Link") or "")
    if not isinstance(payload, dict):
        return ""
    if mode == "token":
        token = payload.get("nextPageToken") or payload.get("next_cursor")
        return _with_query(url, "pageToken", token)
    if mode == "cursor":
        meta = payload.get("response_metadata")
        token = meta.get("next_cursor") if isinstance(meta, dict) else payload.get("next_cursor")
        if not token:
            token = payload.get("next_cursor")
        return _with_query(url, "cursor", token)
    if mode == "next_url":
        return _absolute_next(payload, url)
    if mode == "servicenow":
        return _servicenow_next(payload, url)
    if mode == "offset":
        size = payload.get("size")
        start = payload.get("start")
        limit = payload.get("limit")
        if (
            isinstance(size, int)
            and isinstance(start, int)
            and isinstance(limit, int)
            and size >= limit
        ):
            return _with_query(url, "start", start + limit)
    return ""


def _absolute_next(payload: object, url: str) -> str:
    if not isinstance(payload, dict):
        return ""
    raw = (
        payload.get("nextRecordsUrl")
        or payload.get("next_page")
        or payload.get("nextLink")
        or payload.get("@odata.nextLink")
    )
    if not raw:
        return ""
    text = str(raw)
    if text.startswith("http://") or text.startswith("https://"):
        return text
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}{text if text.startswith('/') else '/' + text}"


def _servicenow_next(payload: object, url: str) -> str:
    if not isinstance(payload, dict):
        return ""
    result = payload.get("result")
    if not isinstance(result, list) or not result:
        return ""
    parsed = urlparse(url)
    pairs = dict(parse_qsl(parsed.query))
    try:
        limit = int(pairs.get("sysparm_limit") or "20")
        offset = int(pairs.get("sysparm_offset") or "0")
    except ValueError:
        return ""
    if len(result) < limit:
        return ""
    return _with_query(url, "sysparm_offset", offset + limit)


def _after_token(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    paging = payload.get("paging")
    if not isinstance(paging, dict):
        return ""
    nxt = paging.get("next")
    if not isinstance(nxt, dict):
        return ""
    token = nxt.get("after")
    return "" if token in {None, ""} else str(token)


def _link(header: str) -> str:
    for part in header.split(","):
        if 'rel="next"' not in part:
            continue
        match = re.search(r"<([^>]+)>", part)
        if match:
            return match.group(1)
    return ""


def _with_query(url: str, key: str, value: object) -> str:
    if value is None or value == "":
        return ""
    parsed = urlparse(url)
    pairs = [(name, item) for name, item in parse_qsl(parsed.query) if name != key]
    pairs.append((key, str(value)))
    return urlunparse(parsed._replace(query=urlencode(pairs)))


def _github_file(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        return payload
    import base64  # noqa: PLC0415

    try:
        text = base64.b64decode(str(payload["content"])).decode("utf-8", errors="replace")
    except ValueError:
        return payload
    return {
        "path": payload.get("path"),
        "text": text[:_TEXT_CAP],
        "truncated": len(text) > _TEXT_CAP,
    }


def _text(payload: object) -> str:
    raw = orjson.dumps(payload).decode()
    if len(raw) > _TEXT_CAP:
        return raw[:_TEXT_CAP]
    return raw


def _fail(code: str, text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}


def _ok(text: str, structured: dict[str, object]) -> dict[str, object]:
    return {"text": text, "structured": structured, "is_error": False}
