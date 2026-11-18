"""Ordered OpenAI-compatible endpoints with a Valkey circuit breaker.

Keys never enter the trace. The report names the endpoint id and the model id
the provider returned. Proof label: unit. A live label needs a real key and a date.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import orjson

from ar_common.settings import get_settings, uses_shared_process_state

if TYPE_CHECKING:
    import uuid

_OPEN_AFTER = 3
_OPEN_S = 30
_RETRYABLE = frozenset({408, 409, 429, 500, 502, 503, 504})


class CircuitOpenError(RuntimeError):
    """Staging or production was asked to keep circuit state in the process."""


def routes_for(store: Any, tenant_id: uuid.UUID) -> list[dict[str, str]]:
    """The tenant's ordered endpoints. Secrets are names, never values."""
    book = getattr(store, "model_routes", None)
    raw = book.get(tenant_id) if isinstance(book, dict) else None
    if not isinstance(raw, list):
        from ar_domain.identity.tenant_settings import settings_for  # noqa: PLC0415

        settings = settings_for(store, tenant_id)
        found = settings.get("model_routes")
        raw = found if isinstance(found, list) else []
    routes: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base_url") or item.get("baseUrl") or "").strip()
        model = str(item.get("model") or "").strip()
        if not base or not model:
            continue
        routes.append(
            {
                "id": str(item.get("id") or model),
                "base_url": base.rstrip("/"),
                "model": model,
                "secret_name": str(item.get("secret_name") or item.get("secretName") or ""),
            }
        )
    return routes


def replace_routes(store: Any, tenant_id: uuid.UUID, routes: list[dict[str, str]]) -> None:
    """Save the ordered list on the store and on tenant settings when that book exists."""
    from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415
    from ar_domain.egress import model_refusal, residency_of  # noqa: PLC0415
    from ar_domain.models.urls import chat_completions_url  # noqa: PLC0415

    for route in routes:
        problem = model_refusal(
            store,
            tenant_id,
            chat_completions_url(route["base_url"]),
            residency=residency_of(store, tenant_id),
        )
        if problem is not None:
            raise ArError(ErrorCode.BAD_REQUEST, problem)
    book = getattr(store, "model_routes", None)
    if not isinstance(book, dict):
        book = {}
        store.model_routes = book
    book[tenant_id] = routes
    settings_book = getattr(store, "tenant_settings", None)
    if isinstance(settings_book, dict):
        current = settings_book.get(tenant_id)
        row = dict(current) if isinstance(current, dict) else {}
        row["model_routes"] = routes
        settings_book[tenant_id] = row


def retryable_status(status: int) -> bool:
    return status in _RETRYABLE or status >= 500


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def circuit_key(tenant_id: uuid.UUID, endpoint_id: str) -> str:
    return f"ar:model-circuit:{tenant_id}:{endpoint_id}"


class CircuitBreaker:
    """Closed, open, then one half-open trial. State is a JSON value on the client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def allow(self, key: str, *, now: float | None = None) -> bool:
        row = self._read(key)
        if row.get("state") != "open":
            return True
        opened = _number(row.get("opened_at"))
        moment = time.time() if now is None else now
        if moment - opened >= _OPEN_S:
            row["state"] = "half_open"
            self._write(key, row)
            return True
        return False

    def success(self, key: str) -> None:
        self._write(key, {"state": "closed", "failures": 0, "opened_at": 0})

    def failure(self, key: str, *, now: float | None = None) -> None:
        row = self._read(key)
        if row.get("state") == "half_open":
            failures = _OPEN_AFTER
        else:
            failures = _whole(row.get("failures")) + 1
        state = "open" if failures >= _OPEN_AFTER else "closed"
        opened = time.time() if now is None else now
        self._write(
            key,
            {
                "state": state,
                "failures": failures,
                "opened_at": opened if state == "open" else 0,
            },
        )

    def _read(self, key: str) -> dict[str, object]:
        raw = self.client.get(key)
        if isinstance(raw, bytes):
            raw = raw.decode()
        if not isinstance(raw, str) or not raw:
            return {"state": "closed", "failures": 0, "opened_at": 0}
        try:
            loaded = orjson.loads(raw)
        except orjson.JSONDecodeError:
            return {"state": "closed", "failures": 0, "opened_at": 0}
        return loaded if isinstance(loaded, dict) else {"state": "closed", "failures": 0}

    def _write(self, key: str, row: dict[str, object]) -> None:
        payload = orjson.dumps(row).decode()
        setter = getattr(self.client, "set", None)
        if not callable(setter):
            return
        try:
            setter(key, payload, ex=_OPEN_S * 4)
        except TypeError:
            setter(key, payload)


class MemoryCircuitClient:
    """Process dict used only in dev and CI. Production must pass Valkey."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        del ex
        self.values[key] = value


def breaker_for(store: Any) -> CircuitBreaker:
    """Valkey when the process has it. Dev and CI may use memory. Staging refuses."""
    client = getattr(store, "valkey_client", None)
    if client is not None:
        return CircuitBreaker(client)
    if uses_shared_process_state(get_settings().env):
        raise CircuitOpenError("staging and production keep model circuit state in Valkey")
    memory = getattr(store, "circuit_memory", None)
    if not isinstance(memory, MemoryCircuitClient):
        memory = MemoryCircuitClient()
        store.circuit_memory = memory
    return CircuitBreaker(memory)


async def routed_completion(  # noqa: PLR0912, PLR0915
    store: Any,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]],
    *,
    tenant_id: uuid.UUID,
    routes: list[dict[str, str]],
    budget_s: float | None = None,
    max_tokens: int | None = None,
    response_format: dict[str, object] | None = None,
) -> dict[str, object]:
    """Try each open endpoint. A timeout, 429, 5xx or bad JSON moves to the next."""
    import httpx  # noqa: PLC0415

    from ar_domain.models.logic import completion_message  # noqa: PLC0415

    breaker = breaker_for(store)
    last = "The model provider did not answer."
    fell_back = False
    for route in routes:
        key = circuit_key(tenant_id, route["id"])
        if not breaker.allow(key):
            fell_back = True
            continue
        headers = authorization_for(store, tenant_id, route)
        from ar_domain.models.urls import chat_completions_url  # noqa: PLC0415

        url = chat_completions_url(route["base_url"])
        from ar_domain.egress import model_refusal, residency_of  # noqa: PLC0415

        problem = model_refusal(store, tenant_id, url, residency=residency_of(store, tenant_id))
        if problem is not None:
            breaker.failure(key)
            last = problem
            fell_back = True
            continue
        from ar_domain.models.call import clamp_timeout  # noqa: PLC0415
        from ar_domain.models.options import request_options_of  # noqa: PLC0415
        from ar_domain.models.request import (  # noqa: PLC0415
            chat_completion_body,
            model_output_limit,
            response_format_body,
        )

        limit = None
        window = None
        registry = None
        options: dict[str, object] = {}
        capabilities: set[str] = set()
        models = getattr(store, "models", {})
        if isinstance(models, dict):
            for row in models.values():
                if isinstance(row, dict) and str(row.get("upstream_model") or "") == route["model"]:
                    limit = model_output_limit(row)
                    raw_window = row.get("context_window")
                    if (
                        isinstance(raw_window, int)
                        and not isinstance(raw_window, bool)
                        and raw_window > 0
                    ):
                        window = raw_window
                    registry = row.get("id")
                    options = request_options_of(row)
                    raw_caps = row.get("capabilities")
                    if isinstance(raw_caps, list):
                        capabilities = {str(item) for item in raw_caps}
                    break
        shaped = None
        if response_format and "json_schema" in capabilities:
            shaped = response_format_body(response_format, mode="json_schema")
        elif response_format and "json_object" in capabilities:
            shaped = response_format_body(response_format, mode="json_object")
        body = chat_completion_body(
            model=route["model"],
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            model_limit=limit,
            context_window=window,
            options=options,
            response_format=shaped,
        )
        try:
            from ar_domain.egress import dial_allow  # noqa: PLC0415

            timeout_s = clamp_timeout(30.0, budget_s)
            if timeout_s <= 0:
                last = "The model provider did not answer."
                fell_back = True
                continue
            from ar_common.internal_http import async_post  # noqa: PLC0415

            response = await async_post(
                url,
                json=body,
                headers=headers,
                timeout_s=timeout_s,
                allow=dial_allow(store, tenant_id),
            )
        except httpx.HTTPError:
            breaker.failure(key)
            last = "The model provider did not answer."
            fell_back = True
            continue
        if retryable_status(response.status_code):
            breaker.failure(key)
            last = "The model provider returned an error."
            fell_back = True
            continue
        if response.status_code >= 300:
            breaker.failure(key)
            last = "The model provider returned an error."
            fell_back = True
            continue
        try:
            payload = response.json()
        except ValueError:
            breaker.failure(key)
            last = "The model provider returned malformed JSON."
            fell_back = True
            continue
        breaker.success(key)
        parsed = completion_message(payload, strip_thinking="preserve_thinking" not in capabilities)
        parsed["real"] = True
        parsed["endpoint_id"] = route["id"]
        from ar_domain.models.logic import resolved_model_label  # noqa: PLC0415

        parsed["resolved_model_id"] = route["model"]
        parsed["answered_model"] = resolved_model_label(route["model"])
        if registry is not None:
            parsed["model_id"] = str(registry)
        parsed["fallback"] = fell_back
        if shaped is not None:
            parsed["response_format_sent"] = True
        return parsed
    return {
        "text": last,
        "tool_calls": [],
        "usage": {"tokens_in": 0, "tokens_out": 0, "usage_source": "unknown"},
        "real": True,
    }


def authorization_for(store: Any, tenant_id: uuid.UUID, route: dict[str, str]) -> dict[str, str]:
    """Bearer from a named secret. The header is not logged or audited."""
    name = route.get("secret_name") or ""
    if not name:
        return {}
    from ar_domain.tools.named_secrets import read_named_secret  # noqa: PLC0415

    token = read_named_secret(store, tenant_id, name)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
