"""Egress decision for the Squid helper. Fail closed."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_common.sandboxkit import DEFAULT_DENY_CIDRS, allowed_hosts, host_denied


def check(store: Any, sandbox_id: str, host: str, token: str) -> int:
    """200 when the host is allowed for that sandbox token, otherwise 403."""
    import uuid  # noqa: PLC0415

    try:
        key = uuid.UUID(sandbox_id)
    except ValueError:
        return 403
    row = store.sandboxes.get(key)
    if not isinstance(row, dict):
        return 403
    digest = row.get("auth_token_hash")
    import hashlib  # noqa: PLC0415

    if not token or digest != hashlib.sha256(token.encode()).hexdigest():
        return 403
    template = store.sandbox_templates.get(row.get("template_id"))
    allow = template.get("egress_allowlist") if isinstance(template, dict) else []
    hosts = allowed_hosts(
        [str(item) for item in allow] if isinstance(allow, list) else [],
        [],
        [],
        mirrors=[],
        allow_packages=False,
        env=os.environ.get("AR_ENV", "dev"),
    )
    if host not in hosts and "*" not in hosts:
        return 403
    allow_loopback = os.environ.get("AR_ENV", "dev") in {"dev", "ci", "test"}
    if host_denied(host, DEFAULT_DENY_CIDRS, _resolve, allow_loopback=allow_loopback):
        return 403
    return 200


def _resolve(host: str) -> list[str]:
    import socket  # noqa: PLC0415

    infos = socket.getaddrinfo(host, None)
    return [str(item[4][0]) for item in infos]
