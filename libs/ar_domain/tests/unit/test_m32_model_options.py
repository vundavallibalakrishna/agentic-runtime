"""Per-model request options replace name-based special cases. Task: M32-T08."""

import uuid

import httpx
import pytest

from ar_domain.chat.service import demo_id
from ar_domain.models.options import (
    apply_request_options,
    copy_request_options,
    default_request_options,
    request_options_of,
)
from ar_domain.models.registry import UpstreamTarget
from ar_model_gateway.upstream import complete_upstream
from ar_testing.demo import demo_store


def test_defaults_and_merge_rules() -> None:
    assert default_request_options("Qwen/Qwen3-32B") == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert default_request_options("gpt-4.1") == {}
    body = {"model": "m", "chat_template_kwargs": {"enable_thinking": True}, "max_tokens": 5}
    merged = apply_request_options(
        body, {"chat_template_kwargs": {"enable_thinking": False, "extra": 1}, "temperature": 0}
    )
    assert merged["chat_template_kwargs"] == {"enable_thinking": True, "extra": 1}
    assert merged["temperature"] == 0
    assert merged["max_tokens"] == 5
    assert request_options_of({"request_options": {"a": 1}}) == {"a": 1}
    assert request_options_of({"request_options": "bad"}) == {}
    stored = copy_request_options({"chat_template_kwargs": {"enable_thinking": False}})
    assert stored == {"chat_template_kwargs": {"enable_thinking": False}}
    # A camelCase provider key is kept, not snake_cased, on the write path.
    echoed = copy_request_options({"chatTemplateKwargs": {"enableThinking": False}})
    assert echoed == {"chatTemplateKwargs": {"enableThinking": False}}


def test_registration_stores_options_and_aliases_resolve_them() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    provider = store.providers[demo_id("provider")]
    qwen = store.create_model(
        tenant, uuid.UUID(str(provider["id"])), "Qwen", "Qwen/Qwen3-32B", "chat", platform=False
    )
    assert qwen["request_options"] == {"chat_template_kwargs": {"enable_thinking": False}}
    other = store.create_model(
        tenant,
        uuid.UUID(str(provider["id"])),
        "Other",
        "mistral-large",
        "chat",
        platform=False,
        request_options={"temperature": 0.2},
    )
    assert other["request_options"] == {"temperature": 0.2}
    alias = store.create_alias(tenant, "quiet", "chat", uuid.UUID(str(qwen["id"])), platform=False)
    assert alias["alias"] == "quiet"
    assert store.request_options(tenant, "quiet") == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert store.request_options(tenant, "missing") == {}


@pytest.mark.asyncio
async def test_gateway_applies_the_target_options(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, object]] = []

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(
            self, _url: str, *, json: dict[str, object], headers: object
        ) -> httpx.Response:
            del headers
            seen.append(json)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=httpx.Request("POST", _url),
            )

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    target = UpstreamTarget(
        base_url="https://provider.example/v1",
        api_key="",
        upstream_model="Qwen/Qwen3-32B",
        timeout_s=10,
        kind="openai_compatible",
        request_options={"chat_template_kwargs": {"enable_thinking": False}},
    )
    await complete_upstream({"model": "alias", "messages": []}, target)
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
    plain = UpstreamTarget(
        base_url="https://provider.example/v1",
        api_key="",
        upstream_model="Qwen/Qwen3-32B",
        timeout_s=10,
        kind="openai_compatible",
    )
    await complete_upstream({"model": "alias", "messages": []}, plain)
    assert "chat_template_kwargs" not in seen[1], "the name alone no longer changes the request"


def test_catalogue_refresh_keeps_prices_and_options() -> None:
    from types import SimpleNamespace

    from ar_domain.models.registry import model_row_from

    record = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider_id=uuid.uuid4(),
        name="priced",
        upstream_model="Qwen/Qwen3-32B",
        kind="chat",
        capabilities=["tools"],
        price_input_micros_per_mtok=100_000,
        price_output_micros_per_mtok=300_000,
        request_options={"chat_template_kwargs": {"enable_thinking": False}},
        status="active",
    )
    row = model_row_from(record)
    assert row["price_input_micros_per_mtok"] == 100_000
    assert row["price_output_micros_per_mtok"] == 300_000
    assert row["request_options"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert row["platform"] is False
