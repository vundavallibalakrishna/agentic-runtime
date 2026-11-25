"""The gate on a browser navigation. The browser itself runs on the agent's computer.

The browser tools drive Chromium inside the sandbox (``sandboxes/runtime.py`` sends
each call there). What is decided here, before a navigation is sent, is whether the
address may be opened: an allowlisted host proceeds, another public host waits for
approval, and a private or metadata address is refused.
"""

from __future__ import annotations

import socket
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ar_common.sandboxkit import DEFAULT_DENY_CIDRS, host_denied
from ar_common.settings import loopback_allowed

if TYPE_CHECKING:
    from typing import Any


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


def click_without_target(name: str, arguments: dict[str, object]) -> dict[str, object] | None:
    """The refusal for a click that names no element, the same wherever the browser runs."""
    if name != "click":
        return None
    if str(arguments.get("ref") or "").strip() or str(arguments.get("text") or "").strip():
        return None
    return _error("validation_failed", "ref or text is required")


def navigate_decision(
    store: Any, sandbox: dict[str, object], arguments: dict[str, object], url: str
) -> dict[str, object] | None:
    """The egress gate for one navigation, applied before the computer is asked.

    Returns an ``egress_denied`` error to stop the navigation (and records the denial), or
    ``None`` to let it proceed. Allowlisted hosts proceed; another public host waits for the
    same approval a write uses; a private or metadata address is denied.
    """
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
    return None


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


def _reject(store: Any, sandbox: dict[str, object], host: str) -> None:
    from ar_domain.sandboxes.runtime import _deny  # noqa: PLC0415

    _deny(store, sandbox, host)


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
