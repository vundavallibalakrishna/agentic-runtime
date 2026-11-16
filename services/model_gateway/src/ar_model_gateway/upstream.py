"""Call a registered OpenAI-compatible provider. Spec: docs/03-specs/04-model-gateway.md."""

import httpx
from fastapi.responses import JSONResponse

from ar_common.egress_http import async_client
from ar_domain.models.logic import completion_text
from ar_domain.models.options import apply_request_options
from ar_domain.models.registry import UpstreamTarget, lookup_upstream
from ar_domain.models.urls import chat_completions_url

_UNAVAILABLE = {
    "error": {"code": "no_healthy_upstream", "message": "the model provider did not answer"}
}


async def forward_registered(
    body: dict[str, object], model_name: str
) -> dict[str, object] | JSONResponse | None:
    """Return an upstream completion, a 502, or None when the model is not registered."""
    target = await lookup_upstream(model_name)
    if target is None:
        return None
    try:
        return await complete_upstream(body, target)
    except httpx.HTTPError:
        return JSONResponse(status_code=502, content=_UNAVAILABLE)


async def complete_upstream(
    body: dict[str, object], target: UpstreamTarget
) -> dict[str, object] | JSONResponse:
    """POST ``/chat/completions`` with the stored key. The key is not copied into the result."""
    payload = dict(body)
    payload["model"] = target.upstream_model
    apply_request_options(payload, target.request_options)
    headers: dict[str, str] = {}
    if target.api_key:
        headers["Authorization"] = f"Bearer {target.api_key}"
    url = chat_completions_url(target.base_url)
    from types import SimpleNamespace  # noqa: PLC0415

    from ar_domain.egress import (  # noqa: PLC0415
        model_refusal,
        residency_of,
    )

    profiles = {}
    settings = {}
    if target.tenant_id is not None:
        profiles[target.tenant_id] = {"data_residency": target.data_residency}
        settings[target.tenant_id] = {"egress_allowlist": list(target.egress_allow)}
    stand = SimpleNamespace(tenant_profiles=profiles, tenant_settings=settings)
    problem = model_refusal(
        stand, target.tenant_id, url, residency=residency_of(stand, target.tenant_id)
    )
    if problem is not None:
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "egress_denied", "message": problem}},
        )
    async with async_client(timeout=float(target.timeout_s)) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    parsed = response.json()
    if not isinstance(parsed, dict):
        raise httpx.HTTPError("upstream payload was not an object")
    text = completion_text(parsed)
    choices = parsed.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            message["content"] = text
            choices[0]["message"] = message
    return parsed
