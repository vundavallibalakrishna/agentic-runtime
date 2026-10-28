"""The gateway calls a registered provider and does not echo its key."""

import httpx
import pytest
from fastapi.testclient import TestClient

from ar_domain.models.registry import UpstreamTarget
from ar_model_gateway.main import create_application


@pytest.mark.asyncio
async def test_registered_model_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    target = UpstreamTarget(
        base_url="https://api.deepinfra.com/v1/openai",
        api_key="sk-cert-secret",
        upstream_model="Qwen/Qwen3-32B",
        timeout_s=30,
        kind="openai_compatible",
    )

    async def _lookup(model_name: str) -> UpstreamTarget | None:
        return target if model_name == "Qwen/Qwen3-32B" else None

    seen: dict[str, object] = {}

    class _Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "<think>x</think>pong"}}]}

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
            seen["headers"] = dict(headers)
            return _Response()

    monkeypatch.setattr("ar_model_gateway.upstream.lookup_upstream", _lookup)
    monkeypatch.setattr("ar_model_gateway.upstream.httpx.AsyncClient", _Client)
    client = TestClient(create_application())
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "Qwen/Qwen3-32B",
            "messages": [{"role": "user", "content": "Say pong"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "pong"
    assert "sk-cert-secret" not in response.text
    assert seen["url"] == "https://api.deepinfra.com/v1/openai/chat/completions"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer sk-cert-secret"
    sent = seen["json"]
    assert isinstance(sent, dict)
    assert sent["chat_template_kwargs"] == {"enable_thinking": False}


def test_unknown_named_model_does_not_fall_back_to_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _missing(_model_name: str) -> None:
        return None

    monkeypatch.setattr("ar_model_gateway.upstream.lookup_upstream", _missing)
    client = TestClient(create_application())
    response = client.post(
        "/v1/chat/completions",
        json={"model": "missing/model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 502
    assert "fake:" not in response.text
    assert "sk-" not in response.text


def test_fake_model_still_echoes(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    client = TestClient(create_application())
    response = client.post(
        "/v1/chat/completions",
        json={"model": "fake-chat", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "fake: hi"
