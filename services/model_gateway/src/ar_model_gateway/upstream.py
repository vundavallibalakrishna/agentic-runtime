"""Call a registered OpenAI-compatible provider. Spec: docs/03-specs/04-model-gateway.md."""

import httpx
from fastapi.responses import JSONResponse

from ar_domain.models.logic import completion_text
from ar_domain.models.registry import UpstreamTarget, lookup_upstream

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


async def complete_upstream(body: dict[str, object], target: UpstreamTarget) -> dict[str, object]:
    """POST ``/chat/completions`` with the stored key. The key is not copied into the result."""
    payload = dict(body)
    payload["model"] = target.upstream_model
    if "qwen3" in target.upstream_model.lower():
        payload.setdefault("chat_template_kwargs", {"enable_thinking": False})
    headers: dict[str, str] = {}
    if target.api_key:
        headers["Authorization"] = f"Bearer {target.api_key}"
    url = target.base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=float(target.timeout_s)) as client:
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
