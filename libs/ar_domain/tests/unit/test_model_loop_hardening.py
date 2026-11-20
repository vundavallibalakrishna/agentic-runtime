"""Open-weight model loop: arguments, timeout, fallback, format, tokens, usage, think tags."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, ClassVar

import pytest

from ar_domain.demo_ids import demo_id
from ar_domain.models.arguments import parse_tool_arguments
from ar_domain.models.call import clamp_timeout
from ar_domain.models.logic import completion_message, completion_text, strip_think
from ar_domain.models.request import chat_completion_body, resolve_max_tokens
from ar_domain.tools.agent_loop import run_agent_loop
from ar_testing.demo import demo_store
from ar_testing.retry_tool import MODEL_NAME, offer_retry_tool


def test_malformed_arguments_are_repaired_or_rejected() -> None:
    fenced = parse_tool_arguments('```json\n{"note": "ready"}\n```')
    assert fenced.ok and fenced.repaired and fenced.arguments == {"note": "ready"}
    trailed = parse_tool_arguments('{"note": "ready"} thanks')
    assert trailed.ok and trailed.arguments == {"note": "ready"}
    commas = parse_tool_arguments('{"note": "ready",}')
    assert commas.ok and commas.arguments == {"note": "ready"}
    quoted = parse_tool_arguments("{'note': 'ready'}")
    assert quoted.ok and quoted.repaired and quoted.arguments == {"note": "ready"}
    broken = parse_tool_arguments("not json")
    assert not broken.ok
    assert broken.arguments == {}
    assert broken.error
    explicit = parse_tool_arguments("{}")
    assert explicit.ok and explicit.arguments == {} and not explicit.error


def test_completion_message_does_not_invent_empty_arguments_or_usage() -> None:
    parsed = completion_message(
        {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "a",
                                "function": {
                                    "name": "session__plan_update",
                                    "arguments": "not json",
                                },
                            },
                            {
                                "id": "a",
                                "function": {"name": "session__search", "arguments": "{}"},
                            },
                            {"function": {"name": "session__search", "arguments": "{}"}},
                        ],
                    }
                }
            ]
        }
    )
    calls = parsed["tool_calls"]
    assert isinstance(calls, list)
    assert calls[0]["arguments_error"]  # type: ignore[index]
    assert calls[0]["arguments"] == {}  # type: ignore[index]
    assert calls[1]["id"] == "a:1"  # type: ignore[index]
    assert calls[2]["id"] == "call_2"  # type: ignore[index]
    usage = parsed["usage"]
    assert isinstance(usage, dict)
    assert usage["usage_source"] == "unknown"
    reported = completion_message(
        {
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
    )
    assert reported["usage"]["usage_source"] == "provider"  # type: ignore[index]


def test_think_tags_leave_the_answer_and_keep_the_trace() -> None:
    assert strip_think("<think>hidden</think>pong") == "pong"
    assert strip_think("<think>only</think>") == ""
    assert completion_text({"choices": [{"message": {"content": "weigh</think>pong"}}]}) == "pong"
    parsed = completion_message(
        {"choices": [{"message": {"content": "<think>hidden</think>pong"}}]}
    )
    assert parsed["text"] == "pong"
    assert parsed["reasoning"] == "hidden"
    kept = completion_message(
        {"choices": [{"message": {"content": "<think>hidden</think>pong"}}]},
        strip_thinking=False,
    )
    assert "<think>" in str(kept["text"])


def test_max_tokens_respects_the_model_and_the_window() -> None:
    assert resolve_max_tokens(800, model_limit=200, context_window=1000, prompt_tokens=10) == 200
    tight = resolve_max_tokens(800, context_window=80, prompt_tokens=40)
    assert tight == 80 - 40 - 16
    body = chat_completion_body(
        model="Qwen/Qwen3-32B",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=800,
        model_limit=200,
        context_window=1000,
        response_format={"type": "json_schema", "json_schema": {"name": "agent_output"}},
    )
    assert body["max_tokens"] == 200
    assert body["response_format"]["type"] == "json_schema"  # type: ignore[index]


def test_timeout_is_the_lesser_of_the_provider_and_the_budget() -> None:
    assert clamp_timeout(120, None) == 120
    assert clamp_timeout(120, 4) == 4
    assert clamp_timeout(120, 0) == 0


def _client(script: list[dict[str, object]], seen: list[dict[str, object]]) -> Any:
    pending = list(script)

    class _Response:
        def __init__(self, status: int, payload: dict[str, object]) -> None:
            self.status_code = status
            self._payload = payload
            self.text = str(payload.get("error") or "")

        def json(self) -> dict[str, object]:
            if self.status_code >= 300 and "choices" not in self._payload:
                raise ValueError("error")
            return self._payload

    class _Client:
        def __init__(self, *_args: object, timeout: float | None = None, **_kwargs: object) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, json: dict[str, object], headers: dict[str, str]
        ) -> _Response:
            del url, headers
            seen.append({"timeout": self.timeout, "body": json})
            item = pending.pop(0) if pending else script[-1]
            return _Response(int(item["status"]), item["payload"])  # type: ignore[arg-type]

        def stream(self, *_args: object, **_kwargs: object) -> _Unstreamed:
            # This provider answers in one piece, so a caller that is listening asks again.
            return _Unstreamed()

    class _Unstreamed:
        status_code = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        async def __aenter__(self) -> _Unstreamed:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    def factory(*_args: object, **kwargs: object) -> _Client:
        return _Client(**kwargs)

    return factory


def _connected(
    *,
    capabilities: list[str] | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    fallback: bool = False,
    default_params: dict[str, object] | None = None,
) -> tuple[Any, uuid.UUID, str, str]:
    store = demo_store(allow_loopback=True)
    tenant = demo_id("tenant")
    created = store.create_provider(
        tenant,
        "upstream",
        "openai_compatible",
        "https://api.deepinfra.com/v1/openai",
        platform=False,
        api_key="sk-test-not-a-real-key",
    )
    provider_id = uuid.UUID(str(created["id"]))
    primary = store.create_model(
        tenant,
        provider_id,
        "Primary",
        "Qwen/Qwen3-32B",
        "chat",
        platform=False,
        capabilities=capabilities,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )
    primary_id = uuid.UUID(str(primary["id"]))
    spare_name = "org/spare"
    fallback_ids: list[uuid.UUID] = []
    if fallback:
        spare = store.create_model(tenant, provider_id, "Spare", spare_name, "chat", platform=False)
        fallback_ids.append(uuid.UUID(str(spare["id"])))
    store.create_alias(
        tenant,
        "reasoning",
        "chat",
        primary_id,
        platform=False,
        fallback_model_ids=fallback_ids,
        default_params=default_params,
    )
    return store, tenant, "Qwen/Qwen3-32B", spare_name


@pytest.mark.asyncio
async def test_a_bad_tool_call_is_returned_to_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    store, tenant, _primary, _spare = _connected()
    offer_retry_tool(store, tenant)
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {
                    "status": 200,
                    "payload": {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "c1",
                                            "function": {
                                                "name": MODEL_NAME,
                                                "arguments": "not json",
                                            },
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                },
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "recovered"}}],
                        "usage": {"prompt_tokens": 4, "completion_tokens": 1},
                    },
                },
            ],
            seen,
        ),
    )
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Save a note", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await store.generate(run_id, "Save a note", [])
    run = store.runs[run_id]
    answer = str(store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"])
    assert "recovered" in answer
    previews = store.messages[uuid.UUID(str(run["assistant_message_id"]))]["tool_calls"]
    assert isinstance(previews, list) and previews
    assert "not valid JSON" in str(previews[0])
    assert run["usage"]["usage_source"] == "mixed"  # type: ignore[index]


@pytest.mark.asyncio
async def test_the_call_timeout_is_clamped_to_the_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, tenant, _primary, _spare = _connected()
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                }
            ],
            seen,
        ),
    )
    parsed = await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        budget_s=4,
    )
    assert parsed is not None and parsed["text"] == "pong"
    assert seen[0]["timeout"] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_retryable_status_uses_the_configured_fallback(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    monkeypatch.setenv("AR_MG_FALLBACK_BACKOFF_S", "0")
    store, tenant, primary, spare = _connected(fallback=True)
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {"status": status, "payload": {"error": "unavailable"}},
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "from spare"}}],
                        "usage": {"prompt_tokens": 2, "completion_tokens": 2},
                    },
                },
            ],
            seen,
        ),
    )
    parsed = await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
    )
    assert parsed is not None
    assert parsed["text"] == "from spare"
    assert parsed["fallback"] is True
    assert parsed["resolved_model_id"] == spare
    assert [item["body"]["model"] for item in seen] == [primary, spare]  # type: ignore[index]


@pytest.mark.asyncio
async def test_response_format_is_sent_only_when_the_model_supports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    store, tenant, _primary, _spare = _connected(capabilities=["json_schema"])
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": '{"answer":"north"}'}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                }
            ],
            seen,
        ),
    )
    await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        response_format=schema,
    )
    sent = seen[0]["body"]["response_format"]  # type: ignore[index]
    assert sent["type"] == "json_schema"
    assert sent["json_schema"]["schema"] == schema
    bare, bare_tenant, _primary, _spare = _connected()
    bare_seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                }
            ],
            bare_seen,
        ),
    )
    await bare.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=bare_tenant,
        model_alias="reasoning",
        response_format=schema,
    )
    assert "response_format" not in bare_seen[0]["body"]  # type: ignore[operator]


@pytest.mark.asyncio
async def test_max_tokens_comes_from_config_and_the_context_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, tenant, _primary, _spare = _connected(
        context_window=1000, max_output_tokens=200, default_params={"max_tokens": 50}
    )
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                }
            ],
            seen,
        ),
    )
    await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        max_tokens=800,
    )
    assert seen[0]["body"]["max_tokens"] == 200  # type: ignore[index]
    await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
    )
    assert seen[1]["body"]["max_tokens"] == 50  # type: ignore[index]


@pytest.mark.asyncio
async def test_a_model_that_omits_usage_is_marked_estimated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)  # type: ignore[method-assign]
    pending = [
        {
            "text": "pong",
            "tool_calls": [],
            "usage": {"tokens_in": 0, "tokens_out": 0, "usage_source": "unknown"},
            "real": True,
        }
    ]

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
        budget_s: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, object] | None = None,
    ) -> dict[str, object]:
        del messages, tools, tenant_id, model_alias, budget_s, max_tokens, response_format
        return pending.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hello", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    assistant = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    assert await run_agent_loop(store, run, assistant, "hello") is True
    usage = run["usage"]
    assert isinstance(usage, dict)
    assert usage["usage_source"] == "estimated"
    assert usage["cost_micros"] == 0
    assert int(usage["tokens_out"]) > 0


def test_argument_parser_rejects_values_that_are_not_objects() -> None:
    assert parse_tool_arguments(None).error == "tool arguments were missing"
    assert not parse_tool_arguments(1).ok
    assert parse_tool_arguments("").error == "tool arguments were empty"
    assert not parse_tool_arguments("x" * 100_001).ok
    nested = parse_tool_arguments('"{\\"note\\": \\"ready\\"}"')
    assert nested.ok and nested.arguments == {"note": "ready"}
    assert not parse_tool_arguments("[1, 2]").ok
    assert not parse_tool_arguments("no braces here").ok


def test_fallback_and_context_policy_read_their_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.models.call import (
        context_length_error,
        fallback_backoff_s,
        max_fallback_hops,
        response_format_rejected,
    )

    monkeypatch.setenv("AR_MG_MAX_FALLBACKS", "nope")
    monkeypatch.setenv("AR_MG_FALLBACK_BACKOFF_S", "-1")
    assert max_fallback_hops() == 2
    assert fallback_backoff_s(2) == 0.4
    monkeypatch.setenv("AR_MG_MAX_FALLBACKS", "1")
    monkeypatch.setenv("AR_MG_FALLBACK_BACKOFF_S", "0")
    assert max_fallback_hops() == 1
    assert fallback_backoff_s(3) == 0
    assert context_length_error(400, "maximum context length exceeded")
    assert not context_length_error(500, "maximum context length exceeded")
    assert response_format_rejected(400, "response_format is unsupported")
    assert not response_format_rejected(400, "bad request")


def test_an_empty_reply_is_sent_back_once() -> None:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)  # type: ignore[method-assign]
    steps = [
        {"text": "   ", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}},
        {"text": "now", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}},
    ]

    async def complete(*_args: object, **_kwargs: object) -> dict[str, object]:
        return steps.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hi", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    assistant = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    asyncio.run(run_agent_loop(store, run, assistant, "hi"))
    assert assistant["text"] == "now"


def _scripted(store: object, steps: list[dict[str, object]]) -> None:
    pending = list(steps)

    async def complete(*_args: object, **_kwargs: object) -> dict[str, object]:
        return pending.pop(0)

    store.complete_turn = complete  # type: ignore[attr-defined]
    store._completion_call = lambda _tenant, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)  # type: ignore[attr-defined]


def _posted(store: object) -> tuple[dict[str, object], dict[str, object]]:
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)  # type: ignore[attr-defined]
    posted = store.post_message(  # type: ignore[attr-defined]
        tenant, user, uuid.UUID(str(conversation["id"])), "hi", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]  # type: ignore[attr-defined]
    assistant = store.messages[uuid.UUID(str(run["assistant_message_id"]))]  # type: ignore[attr-defined]
    return run, assistant


def test_a_context_overflow_is_compacted_and_then_retried() -> None:
    store = demo_store()
    _scripted(
        store,
        [
            {
                "text": "",
                "tool_calls": [],
                "context_length_exceeded": True,
                "usage": {"usage_source": "unknown"},
            },
            {"text": "shorter", "tool_calls": [], "usage": {"tokens_in": 2, "tokens_out": 1}},
        ],
    )
    run, assistant = _posted(store)
    asyncio.run(run_agent_loop(store, run, assistant, "hi"))
    assert assistant["text"] == "shorter"
    assert any(
        isinstance(row.get("detail"), dict) and row["detail"].get("reason") == "context_length"
        for row in store.audit_log
    )


def test_a_repeated_context_overflow_stops_the_run() -> None:
    store = demo_store()
    _scripted(
        store,
        [
            {"text": "", "tool_calls": [], "context_length_exceeded": True, "usage": {}},
            {"text": "", "tool_calls": [], "context_length_exceeded": True, "usage": {}},
        ],
    )
    run, assistant = _posted(store)
    asyncio.run(run_agent_loop(store, run, assistant, "hi"))
    assert run["status"] == "failed"
    assert "too long" in str(assistant.get("text"))


@pytest.mark.asyncio
async def test_json_object_mode_and_a_spent_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    store, tenant, _primary, _spare = _connected(capabilities=["json_object"])
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                }
            ],
            seen,
        ),
    )
    schema = {"type": "object"}
    spent = await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        budget_s=0,
        response_format=schema,
    )
    assert spent is not None and spent.get("budget_exhausted") is True
    assert seen == []
    parsed = await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        response_format=schema,
    )
    assert parsed is not None and parsed["text"] == "pong"
    assert seen[0]["body"]["response_format"] == {"type": "json_object"}  # type: ignore[index]


@pytest.mark.asyncio
async def test_context_length_does_not_switch_models_and_format_can_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AR_MG_FALLBACK_BACKOFF_S", "0")
    store, tenant, primary, _spare = _connected(
        capabilities=["json_schema", "preserve_thinking"], fallback=True
    )
    schema = {"type": "object"}
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ar_domain.chat.service.async_client",
        _client(
            [
                {"status": 400, "payload": {"error": "maximum context length is 8"}},
                {
                    "status": 400,
                    "payload": {"error": "response_format is not supported"},
                },
                {
                    "status": 200,
                    "payload": {
                        "choices": [{"message": {"content": "<think>hidden</think>pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                },
            ],
            seen,
        ),
    )
    blocked = await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        response_format=schema,
    )
    assert blocked is not None and blocked.get("context_length_exceeded") is True
    assert [item["body"]["model"] for item in seen] == [primary]  # type: ignore[index]
    recovered = await store.complete_turn(
        [{"role": "user", "content": "ping"}],
        [],
        tenant_id=tenant,
        model_alias="reasoning",
        response_format=schema,
    )
    assert recovered is not None
    assert recovered.get("response_format_fallback") is True
    assert "<think>" in str(recovered["text"])
    assert [item["body"]["model"] for item in seen] == [primary, primary, primary]  # type: ignore[index]
    assert "response_format" not in seen[-1]["body"]  # type: ignore[operator]
