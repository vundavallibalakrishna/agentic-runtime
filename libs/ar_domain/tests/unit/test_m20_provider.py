"""Registered providers keep the API key out of responses and call the real model."""

import uuid

import httpx
import pytest

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.models.logic import completion_text, strip_think


def test_completion_text_drops_a_think_trace() -> None:
    assert strip_think("<think>hidden</think>pong") == "pong"
    payload = {"choices": [{"message": {"content": "", "reasoning_content": "pong"}}]}
    assert completion_text(payload) == "pong"


def test_provider_response_never_includes_the_api_key() -> None:
    service = ChatService(allow_loopback=True)
    tenant = demo_id("tenant")
    created = service.create_provider(
        tenant,
        "deepinfra",
        "openai_compatible",
        "https://api.deepinfra.com/v1/openai",
        platform=False,
        api_key="sk-cert-secret",
    )
    assert created["has_api_key"] is True
    assert "api_key" not in created
    assert "sk-cert-secret" not in str(created)
    listed = service.list_providers(tenant)
    assert all("sk-cert-secret" not in str(row) for row in listed)


@pytest.mark.asyncio
async def test_chat_calls_the_registered_upstream_model(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatService(allow_loopback=True)
    tenant, user = demo_id("tenant"), demo_id("admin")
    created = service.create_provider(
        tenant,
        "deepinfra",
        "openai_compatible",
        "https://api.deepinfra.com/v1/openai",
        platform=False,
        api_key="sk-cert-secret",
    )
    provider_id = uuid.UUID(str(created["id"]))
    model = service.create_model(
        tenant, provider_id, "Qwen3 32B", "Qwen/Qwen3-32B", "chat", platform=False
    )
    service.create_alias(tenant, "reasoning", "chat", uuid.UUID(str(model["id"])), platform=False)
    seen: dict[str, object] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "<think>hidden</think>pong"}}]}

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(
            self, url: str, json: dict[str, object], headers: dict[str, str]
        ) -> _Response:
            seen["url"] = url
            seen["json"] = json
            seen["headers"] = headers
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    agent_id = next(
        item_id
        for item_id, row in service.agents.items()
        if row.get("slug") == "assistant" and row.get("tenant_id") == tenant
    )
    conversation = service.create_conversation(tenant, user, agent_id)
    posted = service.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Say pong", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await service.generate(run_id, "Say pong", [])
    body = seen["json"]
    assert isinstance(body, dict)
    assert body["model"] == "Qwen/Qwen3-32B"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert "sk-cert-secret" not in str(headers)
    assert "Authorization" not in headers
    assert service.runs[run_id]["result_summary"] == "pong"


@pytest.mark.asyncio
async def test_live_probe_sends_the_key_only_as_a_header(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatService(allow_loopback=True)
    tenant = demo_id("tenant")
    created = service.create_provider(
        tenant,
        "deepinfra",
        "openai_compatible",
        "https://api.deepinfra.com/v1/openai",
        platform=False,
        api_key="sk-cert-secret",
    )
    provider_id = uuid.UUID(str(created["id"]))
    service.create_model(tenant, provider_id, "Qwen3 32B", "Qwen/Qwen3-32B", "chat", platform=False)
    seen: dict[str, object] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "pong"}}]}

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(
            self, url: str, json: dict[str, object], headers: dict[str, str]
        ) -> _Response:
            seen["url"] = url
            seen["headers"] = dict(headers)
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    probed = await service.test_provider(tenant, provider_id)
    assert probed["output"] == "pong"
    assert seen["url"] == "https://api.deepinfra.com/v1/openai/chat/completions"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer sk-cert-secret"
    assert "sk-cert-secret" not in str(probed)
