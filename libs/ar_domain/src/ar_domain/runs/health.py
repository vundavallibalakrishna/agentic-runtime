"""Platform readiness probes. Spec: docs/03-specs/18-observability-eval.md §3."""

import asyncio
from typing import TYPE_CHECKING

import httpx

from ar_common.time import utcnow

if TYPE_CHECKING:
    from collections.abc import Mapping


async def component_health(targets: Mapping[str, str]) -> list[dict[str, object]]:
    """Probe each dependency with a 2 second timeout."""
    async with httpx.AsyncClient(timeout=2.0) as client:
        rows = await asyncio.gather(*(_probe(client, name, url) for name, url in targets.items()))
    return list(rows)


def default_targets(settings: object | None = None) -> dict[str, str]:
    """Known service URLs. An empty URL is reported as not configured."""

    def pick(name: str) -> str:
        value = str(getattr(settings, name, "") or "")
        return value if value.startswith("http") else ""

    return {
        "api": "",
        "temporal": "",
        "postgres": "",
        "valkey": "",
        "retrieval": "",
        "opa": pick("opa_url"),
        "keycloak": pick("oidc_issuer"),
        "object_storage": pick("s3_endpoint"),
        "model_providers": pick("model_gateway_url"),
    }


async def _probe(client: httpx.AsyncClient, name: str, url: str) -> dict[str, object]:
    checked = utcnow().isoformat()
    if not url:
        return {"name": name, "status": "down", "detail": "not configured", "checked_at": checked}
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        return {"name": name, "status": "down", "detail": type(exc).__name__, "checked_at": checked}
    status = "up" if response.status_code < 400 else "degraded"
    if response.status_code >= 500:
        status = "down"
    return {
        "name": name,
        "status": status,
        "detail": str(response.status_code),
        "checked_at": checked,
    }
