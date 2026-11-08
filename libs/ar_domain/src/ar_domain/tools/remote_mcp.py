"""JSON-RPC client for a remote MCP server. Spec: docs/05-contracts/mcp-integration.md.

Streamable HTTP is a POST that returns JSON or an SSE body. Legacy SSE opens a
GET stream, reads the endpoint event, then posts messages. Stdio runs only
inside the general-tool sandbox with network off.
"""

from __future__ import annotations

import contextlib
import queue
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx
import orjson

from ar_common.errors import ArError
from ar_common.http import assert_public_url
from ar_common.isolate import run_isolated
from ar_common.offload import blocking
from ar_common.settings import loopback_allowed
from ar_domain.tools.logic import name_ok, propose_risk

if TYPE_CHECKING:
    from typing import Any

_ARG = re.compile(r"^[A-Za-z0-9_./+=:@-]{1,180}$")


class RemoteError(Exception):
    """The remote server did not return a tool result."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def auth_headers(mode: str, token: str) -> dict[str, str]:
    """Headers for one auth mode. The token never goes into a log line here."""
    if not token or mode in {"none", "basic"}:
        if mode == "basic" and token:
            return {"authorization": f"Basic {token}"}
        return {}
    if mode == "static_secret":
        return {"x-api-key": token}
    return {"authorization": f"Bearer {token}"}


def list_remote(
    store: Any,
    url: str,
    token: str = "",
    mode: str = "none",
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    transport: str = "streamable",
) -> list[dict[str, object]]:
    """Discover tools, following ``nextCursor`` pages in one session. Errors become RemoteError."""
    session: dict[str, str] = {}
    found: list[dict[str, object]] = []
    cursor: str | None = None
    for page in range(100):
        params: dict[str, object] = {"cursor": cursor} if cursor else {}
        payload = _rpc(
            store,
            url,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": params},
            token,
            mode,
            headers=headers,
            timeout=timeout,
            transport=transport,
            initialize=(page == 0),
            session=session,
        )
        found.extend(_tools_page(payload))
        cursor = _next_cursor(payload)
        if not cursor:
            break
    if not found:
        raise RemoteError("tools/list returned no tools")
    return found


def _next_cursor(payload: dict[str, object]) -> str | None:
    result = payload.get("result")
    cursor = result.get("nextCursor") if isinstance(result, dict) else None
    return str(cursor) if isinstance(cursor, str) and cursor else None


def _tools_page(payload: dict[str, object]) -> list[dict[str, object]]:
    """The tools in one ``tools/list`` page, or an empty list. It does not raise."""
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
        return []
    return _tools_from(payload)


def call_remote(  # noqa: PLR0917
    store: Any,
    url: str,
    name: str,
    arguments: dict[str, object],
    token: str,
    mode: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    transport: str = "streamable",
    run_id: object = None,
) -> dict[str, object]:
    """Call one tool. The result is untrusted text for the wrapper.

    Within a run, calls to the same server reuse one MCP session (M39-T06a), so the
    server is initialised once; a dropped session is re-initialised once.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    session = _run_session(store, url, run_id)
    for attempt in range(2):
        try:
            payload = _rpc(
                store,
                url,
                body,
                token,
                mode,
                headers=headers,
                timeout=timeout,
                transport=transport,
                initialize=not (session is not None and bool(session.get("id"))),
                session=session,
            )
            return _result_text(payload)
        except RemoteError:
            # A dropped session: forget its id and initialise a fresh one, once.
            if attempt == 0 and session is not None and session.get("id"):
                session.clear()
                continue
            raise
    return _result_text({})


def _run_session(store: Any, url: str, run_id: object) -> dict[str, str] | None:
    """The MCP session this run holds for ``url``, or None when no run is named.

    The sessions live in process memory, keyed by server and run; another worker that
    picks up the run initialises its own. That is the same process-local posture as the
    rest of a turn's live state (OQ-59).
    """
    if run_id is None:
        return None
    existing = getattr(store, "mcp_sessions", None)
    cache: dict[Any, Any]
    if isinstance(existing, dict):
        cache = existing
    else:
        cache = {}
        with contextlib.suppress(Exception):
            store.mcp_sessions = cache
        if getattr(store, "mcp_sessions", None) is not cache:
            return None
    key = (str(url), str(run_id))
    session = cache.get(key)
    if not isinstance(session, dict):
        session = {}
        cache[key] = session
    return session


def list_stdio(store: Any, command: list[str], *, timeout: int = 20) -> list[dict[str, object]]:
    """Discover tools from a stdio server inside the sandbox."""
    payload = _stdio(
        store,
        command,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        timeout=timeout,
    )
    return _tools_from(payload)


def call_stdio(
    store: Any,
    command: list[str],
    name: str,
    arguments: dict[str, object],
    *,
    timeout: int = 20,
) -> dict[str, object]:
    """Call one stdio tool. Network stays off."""
    payload = _stdio(
        store,
        command,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        timeout=timeout,
    )
    return _result_text(payload)


def safe_command(argv: object) -> list[str]:
    """Accept a short argument list whose program lives on the interpreter path."""
    if not isinstance(argv, list) or not argv or len(argv) > 8:
        raise RemoteError("stdio command must be a short argument list")
    parts = [str(item) for item in argv]
    if any(_ARG.match(part) is None for part in parts):
        raise RemoteError("stdio command has an unsupported character")
    program = parts[0]
    if Path(program).name not in {"python", "python3", "node", "npx", "uv", "uvx"}:
        raise RemoteError("stdio programs must be python, node, npx or uv")
    flags = {"-m", "-y"}
    if any(
        part in {"-c", "-e"} or (part.startswith("-") and part not in flags) or ".." in part
        for part in parts[1:]
    ):
        raise RemoteError("stdio arguments cannot change the interpreter or leave the workspace")
    resolved = program if "/" in program else shutil.which(program)
    if not resolved or not Path(resolved).is_file():
        raise RemoteError("stdio program was not found")
    path = str(Path(resolved).resolve())
    interpreter = str(Path(sys.executable).resolve())
    if path != interpreter and not (
        path.startswith("/usr/") or path.startswith("/bin/") or path.startswith(sys.prefix)
    ):
        raise RemoteError("stdio programs must come from the interpreter or the system bin")
    return [path, *parts[1:]]


def _mcp_name(raw: str) -> str:
    """Turn a remote tool name into the registry's lowercase form."""
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in raw)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")[:48]
    if cleaned and not cleaned[0].isalpha():
        cleaned = f"tool_{cleaned}"[:48]
    return cleaned if name_ok(cleaned) else ""


def _tools_from(payload: dict[str, object]) -> list[dict[str, object]]:
    result = payload.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise RemoteError("tools/list returned no tools")
    found: list[dict[str, object]] = []
    for item in tools:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        raw_notes = item.get("annotations")
        notes = dict(raw_notes) if isinstance(raw_notes, dict) else {}
        raw_name = str(item["name"])
        name = _mcp_name(raw_name)
        if not name:
            continue
        notes["_mcp_name"] = raw_name
        found.append(
            {
                "name": name,
                "title": item.get("title") or raw_name,
                "description": item.get("description") or raw_name,
                "input_schema": item.get("inputSchema") or {"type": "object"},
                "risk_class": propose_risk("remote_mcp", annotations=notes),
                "annotations": notes,
            }
        )
    return found


def _result_text(payload: dict[str, object]) -> dict[str, object]:
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "upstream error")
        code = "schema_changed" if error.get("code") == -32602 else "upstream_error"
        return {"text": message, "structured": {}, "is_error": True, "code": code}
    result = payload.get("result")
    if not isinstance(result, dict):
        return {"text": "", "structured": {}, "is_error": False}
    text = _blocks_text(result)
    is_error = result.get("isError") is True
    outcome: dict[str, object] = {
        "text": text or ("upstream error" if is_error else ""),
        # The whole result is kept, so every content block (text, image, resource)
        # survives for the model and the UI, not only the first text block (A15).
        "structured": result,
        "is_error": is_error,
    }
    if is_error:
        outcome["code"] = "upstream_error"
    return outcome


def _blocks_text(result: dict[str, object]) -> str:
    """Join every content block into one readable result. Images and resources are named."""
    content = result.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text":
                parts.append(str(block.get("text") or ""))
            elif kind == "image":
                parts.append(f"[image: {block.get('mimeType') or 'image'}]")
            elif kind == "resource":
                resource = block.get("resource")
                if isinstance(resource, dict):
                    parts.append(
                        str(resource.get("text") or "")
                        or f"[resource: {resource.get('uri') or ''}]"
                    )
    if not parts and "text" in result:
        parts.append(str(result.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _rpc(
    store: Any,
    url: str,
    body: dict[str, object],
    token: str,
    mode: str,
    *,
    headers: dict[str, str] | None,
    timeout: float,
    transport: str,
    initialize: bool,
    session: dict[str, str] | None = None,
) -> dict[str, object]:
    _guard(store, url)
    sent = dict(headers or auth_headers(mode, token))
    last: RemoteError | None = None
    for attempt in range(2):
        try:
            if transport == "sse":
                return _sse(store, url, body, sent, timeout, initialize=initialize)
            return _post_streamable(
                store, url, body, sent, timeout, initialize=initialize, session=session
            )
        except RemoteError as exc:
            last = exc
            if attempt == 0 and exc.reason == "the remote server did not answer":
                continue
            raise
    raise last or RemoteError("the remote server did not answer")


def _post_streamable(
    store: Any,
    url: str,
    body: dict[str, object],
    headers: dict[str, str],
    timeout: float,
    *,
    initialize: bool,
    session: dict[str, str] | None = None,
) -> dict[str, object]:
    extra = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    merged = {**headers, **extra}
    # A caller may pass a session dict to keep one MCP session across several requests,
    # such as the pages of a tools/list. Without one, each call opens its own.
    held = session if session is not None else {}

    def post(payload: dict[str, object]) -> dict[str, object]:
        sent = dict(merged)
        if held.get("id"):
            sent["mcp-session-id"] = held["id"]
        loaded, response_headers = _post_once(store, url, payload, sent, timeout)
        token = response_headers.get("mcp-session-id")
        if token:
            held["id"] = token
        return loaded

    if initialize and body.get("method") != "initialize":
        post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "agentic-runtime", "version": "1.0.0"},
                },
            }
        )
        with contextlib.suppress(RemoteError):
            post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return post(body)


def _post_once(
    store: Any, url: str, body: dict[str, object], headers: dict[str, str], timeout: float
) -> tuple[dict[str, object], dict[str, str]]:
    transport = getattr(store, "mcp_transport", None)
    try:
        with httpx.Client(transport=transport, timeout=timeout) as client:
            response = blocking(client.post, url, json=body, headers=headers)
            response.raise_for_status()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            if response.status_code in {202, 204} or not response.content:
                return {}, response_headers
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                loaded = _json_from_sse(response.text, expected=body.get("id"))
            else:
                loaded = response.json()
    except httpx.HTTPError as exc:
        raise RemoteError("the remote server did not answer") from exc
    if not isinstance(loaded, dict):
        raise RemoteError("the remote server returned an unexpected body")
    return loaded, response_headers


def _sse(
    store: Any,
    url: str,
    body: dict[str, object],
    headers: dict[str, str],
    timeout: float,
    *,
    initialize: bool,
) -> dict[str, object]:
    """Legacy SSE: read the endpoint event, then post the JSON-RPC body."""
    transport = getattr(store, "mcp_transport", None)
    found: queue.Queue[tuple[str, str]] = queue.Queue()

    def _read() -> None:
        try:
            with (
                httpx.Client(transport=transport, timeout=httpx.Timeout(timeout)) as client,
                client.stream(
                    "GET", url, headers={**headers, "accept": "text/event-stream"}
                ) as response,
            ):
                response.raise_for_status()
                event = "message"
                data: list[str] = []
                for line in response.iter_lines():
                    if line == "":
                        if data:
                            found.put((event, "\n".join(data)))
                        event = "message"
                        data = []
                        continue
                    if line.startswith("event:"):
                        event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data.append(line.split(":", 1)[1].strip())
        except httpx.HTTPError:
            found.put(("error", "the remote server did not answer"))

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    try:
        event, data = blocking(found.get, timeout=timeout)
    except queue.Empty as exc:
        raise RemoteError("the remote server did not answer") from exc
    if event == "error":
        raise RemoteError(data or "the remote server did not answer")
    if event not in {"endpoint", "message"}:
        raise RemoteError("the remote server returned an unexpected body")
    endpoint = data if event == "endpoint" else url
    target = urljoin(url, endpoint)
    _guard(store, target)
    message = body
    if initialize:
        _post_once(
            store,
            target,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agentic-runtime", "version": "1.0.0"},
                },
            },
            {**headers, "content-type": "application/json"},
            timeout,
        )
    posted, _headers = _post_once(
        store, target, message, {**headers, "content-type": "application/json"}, timeout
    )
    if posted.get("result") is not None or posted.get("error") is not None:
        return posted
    try:
        event, data = blocking(found.get, timeout=timeout)
    except queue.Empty as exc:
        raise RemoteError("the remote server did not answer") from exc
    loaded = _json_from_sse(f"event: {event}\ndata: {data}\n\n", expected=body.get("id"))
    if not isinstance(loaded, dict):
        raise RemoteError("the remote server returned an unexpected body")
    return loaded


def _stdio(
    store: Any, command: list[str], body: dict[str, object], *, timeout: int
) -> dict[str, object]:
    del store
    argv = safe_command(command)
    root = Path(tempfile.mkdtemp(prefix="ar-mcp-stdio-"))
    frames = [
        _frame(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agentic-runtime", "version": "1.0.0"},
                },
            }
        ),
        _frame({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        _frame(body),
    ]
    try:
        result = blocking(
            run_isolated,
            root,
            argv,
            timeout=max(1, timeout),
            network=False,
            stdin=b"".join(frames),
        )
    except OSError as exc:
        raise RemoteError("the stdio server did not start") from exc
    if result.exit_code not in {0, None} and not result.stdout.strip():
        raise RemoteError(result.stderr.strip() or "the stdio server did not answer")
    loaded = _frames(result.stdout, expected=body.get("id"))
    if loaded is None:
        raise RemoteError("the stdio server returned an unexpected body")
    return loaded


def _frame(payload: dict[str, object]) -> bytes:
    raw = orjson.dumps(payload)
    return f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw


def _frames(text: str, *, expected: object) -> dict[str, object] | None:
    if "Content-Length:" in text:
        chunks = text.split("Content-Length:")
        for chunk in chunks[1:]:
            parts = chunk.split("\r\n\r\n", 1)
            if len(parts) != 2:
                parts = chunk.split("\n\n", 1)
            if len(parts) != 2:
                continue
            try:
                length = int(parts[0].strip().split("\r\n", 1)[0])
            except ValueError:
                continue
            raw = parts[1].encode()[:length]
            try:
                loaded = orjson.loads(raw)
            except orjson.JSONDecodeError:
                continue
            if isinstance(loaded, dict) and (expected is None or loaded.get("id") == expected):
                return loaded
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            loaded = orjson.loads(line)
        except orjson.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and (expected is None or loaded.get("id") == expected):
            return loaded
    return None


def _json_from_sse(text: str, *, expected: object) -> dict[str, object]:
    data: list[str] = []
    chosen: dict[str, object] | None = None
    for line in text.splitlines():
        if line.startswith("data:"):
            data.append(line.split(":", 1)[1].strip())
        if line == "" and data:
            raw = "\n".join(data)
            data = []
            try:
                loaded = orjson.loads(raw)
            except orjson.JSONDecodeError:
                continue
            if (
                isinstance(loaded, dict)
                and (expected is None or loaded.get("id") in {None, expected})
                and (loaded.get("id") == expected or chosen is None)
            ):
                chosen = loaded
    if chosen is None:
        raise RemoteError("the remote server returned an unexpected body")
    return chosen


def _guard(store: Any, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteError("a remote server needs an http(s) URL")
    host = parsed.hostname or ""
    if _loopback(host) and loopback_allowed():
        return
    resolver = getattr(store, "mcp_resolver", None)
    allow = getattr(store, "mcp_allow_hosts", ())
    hosts = allow if isinstance(allow, tuple | list) else ()
    try:
        if callable(resolver):
            assert_public_url(url, resolver=resolver, allow_hosts=hosts)
        else:
            assert_public_url(url, allow_hosts=hosts)
    except ArError as exc:
        raise RemoteError(str(exc)) from exc


def _loopback(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"}
