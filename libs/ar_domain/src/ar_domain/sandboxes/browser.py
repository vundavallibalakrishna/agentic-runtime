"""Controlled browser session on the M6 computer.

The page engine is in-process HTML (OQ-87). Chromium is optional and stays out
of the sandbox image CI does not build. Cookies live on one sandbox context
and are never copied onto another tenant, conversation or run.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from html.parser import HTMLParser
from typing import TYPE_CHECKING, cast
from urllib.parse import urlencode, urljoin, urlparse

import httpx

from ar_common.offload import blocking
from ar_common.sandboxkit import DEFAULT_DENY_CIDRS, accessibility_tree, host_denied
from ar_common.settings import loopback_allowed

if TYPE_CHECKING:
    from typing import Any

_MAX_HTML = 500_000
_MAX_HOPS = 4
_CHROMIUM = ("chromium", "chromium-browser", "google-chrome")


def navigation_class(store: Any, request: dict[str, object], url: str) -> str:
    """``allow``, ``approve`` or ``deny`` for one navigation URL.

    Allowlisted hosts proceed. Other public hosts wait for approval, the same
    elevation ``general.http`` uses for a write. Private and metadata addresses
    are denied even after approval.
    """
    host = _host(url)
    if host is None or _denied(store, host):
        return "deny"
    template = _template_for(store, request)
    sandbox = {
        "tenant_id": request.get("tenant_id"),
        "agent_id": request.get("agent_id"),
    }
    if _permits(store, sandbox, template, host):
        return "allow"
    return "approve"


def apply_browser(
    store: Any,
    sandbox: dict[str, object],
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    """Run one browser tool against the sandbox's own page context."""
    session = open_context(sandbox, arguments)
    if name == "navigate":
        return _navigate(store, sandbox, session, arguments, str(arguments.get("url") or ""))
    if name == "snapshot":
        return _snapshot(session, _chars(arguments.get("max_chars"), 40000))
    if name in {"click", "type", "press", "scroll", "submit_form"}:
        return _gesture(store, sandbox, session, name, arguments)
    return _error("unknown_tool", name)


def _gesture(
    store: Any,
    sandbox: dict[str, object],
    session: dict[str, object],
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    ref = str(arguments.get("ref") or "")
    if name == "click":
        return _click(store, sandbox, session, arguments, ref)
    if name == "type":
        return _type(session, ref, str(arguments.get("text") or ""))
    if name == "press":
        session["pressed"] = str(arguments.get("key") or ref)
        return _snapshot(session, 4000)
    if name == "scroll":
        _scroll(session, arguments)
        return _snapshot(session, 4000)
    return _submit(store, sandbox, session, arguments, ref)


def open_context(sandbox: dict[str, object], arguments: dict[str, object]) -> dict[str, object]:
    """Return the page context for this run, or the active one when no run is set."""
    sessions = sandbox.get("browser_sessions")
    if not isinstance(sessions, dict):
        sessions = {}
        sandbox["browser_sessions"] = sessions
    tenant = str(sandbox.get("tenant_id") or "")
    run = arguments.get("_run_id")
    if run:
        key = f"run:{run}"
        current: dict[str, object] = _owned(sessions.get(key), tenant) or _fresh(tenant)
    else:
        active = sandbox.get("browser_active")
        key = active if isinstance(active, str) else "sandbox"
        found = _owned(sessions.get(key), tenant)
        if found is None:
            key = "sandbox"
            found = _owned(sessions.get(key), tenant) or _fresh(tenant)
        current = found
    sessions[key] = current
    sandbox["browser_active"] = key
    current["tenant_id"] = tenant
    sandbox["browser"] = current
    return current


def chromium_canary(url: str) -> dict[str, str]:
    """Open one URL in headless Chromium when a binary is installed.

    A missing or unusable binary is ``not_live``. The probe flags are not the
    isolation boundary. The unit job does not install Chromium and does not
    build ``images/sandbox/Dockerfile``.
    """
    binary = next((found for name in _CHROMIUM if (found := shutil.which(name))), "")
    if not binary:
        return {
            "status": "not_live",
            "engine": "chromium",
            "reason": "chromium is not installed",
        }
    profile = tempfile.mkdtemp(prefix="ar-chromium-")
    try:
        completed = blocking(
            lambda: subprocess.run(  # noqa: S603
                [
                    binary,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    url,
                ],
                check=False,
                capture_output=True,
                timeout=15,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": os.environ.get("HOME", tempfile.gettempdir()),
                },
            )
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "not_live", "engine": "chromium", "reason": str(exc)[:200]}
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    text = completed.stdout.decode("utf-8", errors="replace")
    if completed.returncode != 0 or ("Fixture" not in text and "<" not in text):
        detail = completed.stderr.decode("utf-8", errors="replace")[:200]
        return {"status": "not_live", "engine": "chromium", "reason": detail or "chromium exited"}
    return {"status": "live", "engine": "chromium", "excerpt": text[:500]}


def _navigate(
    store: Any,
    sandbox: dict[str, object],
    session: dict[str, object],
    arguments: dict[str, object],
    url: str,
) -> dict[str, object]:
    kind = _class_for(store, sandbox, arguments, url)
    if kind == "deny" or (kind == "approve" and not arguments.get("_browser_cleared")):
        _reject(store, sandbox, _host(url) or url)
        if kind == "approve":
            return _error(
                "egress_denied",
                f"{_host(url) or url} is not on the egress allow list. "
                "browser.navigate waits for approval before opening it.",
            )
        return _error("egress_denied", f"{_host(url) or url} is not on the egress allow list")
    return _exchange(store, sandbox, session, arguments, "GET", url, None, cleared=True)


def _click(
    store: Any,
    sandbox: dict[str, object],
    session: dict[str, object],
    arguments: dict[str, object],
    ref: str,
) -> dict[str, object]:
    element = _element(session, ref)
    href = str(element.get("href") or "")
    if not href or href.startswith("#"):
        return _snapshot(session, 4000)
    target = urljoin(str(session.get("url") or ""), href)
    current = str(session.get("url") or "")
    same = _same_host(current, target)
    kind = _class_for(store, sandbox, arguments, target)
    if same and kind != "deny":
        return _exchange(store, sandbox, session, arguments, "GET", target, None, cleared=True)
    if kind == "allow":
        return _exchange(store, sandbox, session, arguments, "GET", target, None, cleared=True)
    host = _host(target) or target
    _reject(store, sandbox, host)
    if kind == "approve":
        return _error(
            "egress_denied",
            f"{host} is not on the egress allow list. Call browser.navigate so it can be approved.",
        )
    return _error("egress_denied", f"{host} is not on the egress allow list")


def _type(session: dict[str, object], ref: str, text: str) -> dict[str, object]:
    element = _element(session, ref)
    element["value"] = text
    field = str(element.get("field") or "")
    if field:
        fields = session.get("fields")
        bag = fields if isinstance(fields, dict) else {}
        bag[field] = text
        session["fields"] = bag
    return _snapshot(session, 4000)


def _submit(
    store: Any,
    sandbox: dict[str, object],
    session: dict[str, object],
    arguments: dict[str, object],
    ref: str,
) -> dict[str, object]:
    action = _form_action(str(session.get("html") or ""), str(session.get("url") or ""))
    session["submitted"] = ref
    if not action:
        return _snapshot(session, 4000)
    kind = _class_for(store, sandbox, arguments, action)
    same = _same_host(str(session.get("url") or ""), action)
    allowed = kind == "allow" or (same and kind != "deny")
    if kind == "deny" or (not allowed and not arguments.get("_browser_cleared")):
        _reject(store, sandbox, _host(action) or action)
        return _error("egress_denied", f"{_host(action) or action} is not on the egress allow list")
    fields = session.get("fields")
    body = fields if isinstance(fields, dict) else {}
    encoded = urlencode({str(key): str(value) for key, value in body.items()})
    opened = arguments.get("_browser_cleared") is True or allowed
    return _exchange(store, sandbox, session, arguments, "POST", action, encoded, cleared=opened)


def _exchange(  # noqa: PLR0917
    store: Any,
    sandbox: dict[str, object],
    session: dict[str, object],
    arguments: dict[str, object],
    method: str,
    url: str,
    body: str | None,
    *,
    cleared: bool,
) -> dict[str, object]:
    current = url
    start = url
    verb = method
    payload = body
    try:
        with _client(store) as client:
            for _hop in range(_MAX_HOPS):
                if not _hop_allowed(store, sandbox, arguments, start, current, cleared=cleared):
                    _reject(store, sandbox, _host(current) or current)
                    return _error(
                        "egress_denied",
                        f"{_host(current) or current} is not on the egress allow list",
                    )
                host = _host(current) or ""
                headers = {"User-Agent": "AgenticRuntime-Browser"}
                cookie = _cookie_header(session, host)
                if cookie:
                    headers["Cookie"] = cookie
                content = None
                if payload is not None and verb != "GET":
                    content = payload.encode("utf-8")
                response = blocking(client.request, verb, current, headers=headers, content=content)
                _store_cookies(session, host, response.headers)
                location = response.headers.get("location")
                if response.status_code in {301, 302, 303, 307, 308} and location:
                    current = urljoin(current, location)
                    if response.status_code in {301, 302, 303}:
                        verb = "GET"
                        payload = None
                    continue
                html = response.text[:_MAX_HTML]
                session["fields"] = {}
                return _remember(session, current, html, response.status_code)
    except httpx.HTTPError:
        return _error("upstream_error", "the page could not be fetched")
    return _error("egress_denied", "Too many redirects.")


def _snapshot(session: dict[str, object], max_chars: int) -> dict[str, object]:
    text, title = _render(session, max_chars)
    return {
        "text": text or "empty page",
        "structured": {
            "url": session.get("url") or "",
            "title": title,
            "untrusted": True,
            "engine": "fixture",
            "scroll": session.get("scroll") or 0,
        },
        "is_error": False,
    }


def _remember(session: dict[str, object], url: str, html: str, status: int) -> dict[str, object]:
    session["url"] = url
    session["html"] = html
    session["status"] = status
    text, title = _render(session, 40000)
    return {
        "text": text,
        "structured": {
            "url": url,
            "title": title,
            "status": status,
            "untrusted": True,
            "engine": "fixture",
        },
        "is_error": False,
    }


def _render(session: dict[str, object], max_chars: int) -> tuple[str, str]:
    html = str(session.get("html") or "")
    text, title, elements = accessibility_tree(html, max_chars=max(1, min(max_chars, 40000)))
    _bind_fields(html, elements)
    _restore_values(session, elements)
    session["elements"] = elements
    session["title"] = title
    scroll = session.get("scroll")
    offset = scroll if isinstance(scroll, int) else 0
    lines = text.splitlines()
    if offset > 0:
        lines = lines[offset:] or lines[-1:]
    shown = "\n".join(lines)
    if len(shown) > max_chars:
        shown = shown[:max_chars]
    return shown, title


def _scroll(session: dict[str, object], arguments: dict[str, object]) -> None:
    amount = _chars(arguments.get("amount"), 1)
    amount = max(1, min(amount, 10))
    direction = str(arguments.get("direction") or "down")
    current = session.get("scroll")
    origin = current if isinstance(current, int) else 0
    session["scroll"] = max(0, origin - amount) if direction == "up" else origin + amount


def _hop_allowed(
    store: Any,
    sandbox: dict[str, object],
    arguments: dict[str, object],
    start: str,
    current: str,
    *,
    cleared: bool,
) -> bool:
    kind = _class_for(store, sandbox, arguments, current)
    if kind == "deny":
        return False
    if kind == "allow":
        return True
    return cleared and (current == start or _same_host(start, current))


def _class_for(
    store: Any, sandbox: dict[str, object], arguments: dict[str, object], url: str
) -> str:
    request = {
        "tenant_id": sandbox.get("tenant_id") or arguments.get("_tenant_id"),
        "agent_id": arguments.get("_agent_id") or sandbox.get("agent_id"),
        "agent_version_id": arguments.get("_agent_version_id"),
    }
    return navigation_class(store, request, url)


def _permits(
    store: Any, sandbox: dict[str, object], template: dict[str, object], host: str
) -> bool:
    from ar_domain.sandboxes.runtime import host_permitted  # noqa: PLC0415

    return host_permitted(store, sandbox, template, host)


def _template_for(store: Any, request: dict[str, object]) -> dict[str, object]:
    version_id = request.get("agent_version_id")
    if not isinstance(version_id, uuid.UUID):
        version_id = _as_uuid(version_id)
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else {}
    spec = definition.get("sandbox") if isinstance(definition, dict) else {}
    slug = "python-data"
    if isinstance(spec, dict) and spec.get("template"):
        slug = str(spec["template"])
    tenant = request.get("tenant_id")
    templates = getattr(store, "sandbox_templates", {})
    if not isinstance(templates, dict):
        return {}
    for row in templates.values():
        if not isinstance(row, dict) or row.get("slug") != slug:
            continue
        owner = row.get("tenant_id")
        if owner is None or owner == tenant:
            return row
    return {}


def _denied(store: Any, host: str) -> bool:
    def resolve(name: str) -> list[str]:
        custom = getattr(store, "browser_resolve", None)
        if custom is not None:
            found = custom(name)
            return [str(item) for item in found]
        return _resolve(name)

    return host_denied(host, DEFAULT_DENY_CIDRS, resolve, allow_loopback=loopback_allowed())


def _resolve(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None)
    return [str(item[4][0]) for item in infos]


def _host(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    return host or None


def _same_host(current: str, target: str) -> bool:
    left = _host(current)
    right = _host(target)
    return bool(left and right and left == right)


def _reject(store: Any, sandbox: dict[str, object], host: str) -> None:
    from ar_domain.sandboxes.runtime import _deny  # noqa: PLC0415

    _deny(store, sandbox, host)


def _client(store: Any) -> httpx.Client:
    transport = getattr(store, "browser_transport", None)
    if transport is not None:
        return httpx.Client(transport=transport, follow_redirects=False, timeout=5.0)
    return httpx.Client(follow_redirects=False, timeout=5.0)


def _cookie_header(session: dict[str, object], host: str) -> str:
    jar = session.get("cookies")
    if not isinstance(jar, dict):
        return ""
    pairs = jar.get(host)
    if not isinstance(pairs, dict) or not pairs:
        return ""
    return "; ".join(f"{name}={value}" for name, value in pairs.items())


def _store_cookies(session: dict[str, object], host: str, headers: httpx.Headers) -> None:
    if not host:
        return
    jar = session.get("cookies")
    bag = jar if isinstance(jar, dict) else {}
    host_jar = bag.get(host)
    pairs = dict(host_jar) if isinstance(host_jar, dict) else {}
    for raw in headers.get_list("set-cookie"):
        name, value = _cookie_pair(raw)
        if name:
            pairs[name] = value
    bag[host] = pairs
    session["cookies"] = bag


def _cookie_pair(raw: str) -> tuple[str, str]:
    pair = raw.split(";", 1)[0]
    if "=" not in pair:
        return "", ""
    name, value = pair.split("=", 1)
    name = name.strip()
    if not name or name.lower() in {"path", "domain", "expires", "max-age"}:
        return "", ""
    return name, value.strip()


def _form_action(html: str, current: str) -> str:
    parser = _FormParser()
    parser.feed(html)
    if not parser.found:
        return ""
    return urljoin(current, parser.action or current)


def _bind_fields(html: str, elements: list[dict[str, str]]) -> None:
    parser = _FieldParser()
    parser.feed(html)
    inputs = [item for item in elements if item.get("tag") in {"input", "textarea", "select"}]
    for element, name in zip(inputs, parser.names, strict=False):
        element["field"] = name


def _restore_values(session: dict[str, object], elements: list[dict[str, str]]) -> None:
    fields = session.get("fields")
    if not isinstance(fields, dict):
        return
    for element in elements:
        field = element.get("field")
        if field and field in fields:
            element["value"] = str(fields[field])


def _element(session: dict[str, object], ref: str) -> dict[str, str]:
    elements = session.get("elements")
    if isinstance(elements, list):
        for item in elements:
            if isinstance(item, dict) and item.get("ref") == ref:
                return cast("dict[str, str]", item)
    return {"ref": ref, "tag": "button", "name": ref, "href": "", "value": ""}


def _owned(value: object, tenant: str) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    owner = str(value.get("tenant_id") or "")
    if owner not in {"", tenant}:
        return None
    return value


def _fresh(tenant: str) -> dict[str, object]:
    return {
        "tenant_id": tenant,
        "url": "",
        "html": "",
        "title": "",
        "elements": [],
        "cookies": {},
        "fields": {},
        "scroll": 0,
    }


def _chars(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found = False
        self.action = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "form" or self.found:
            return
        self.found = True
        data = {key: value or "" for key, value in attrs}
        self.action = data.get("action", "")


class _FieldParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.names: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"input", "textarea", "select"}:
            return
        data = {key: value or "" for key, value in attrs}
        name = data.get("name") or data.get("aria-label") or data.get("id") or ""
        if name:
            self.names.append(name)
