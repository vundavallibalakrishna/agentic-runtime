"""Assistant tool calls, unbacked claims, and dev-id remaps."""

import uuid

import httpx
import pytest

from ar_domain.agents.logic import assistant_definition, enable_assistant_tools
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.bind import _remap
from ar_domain.models.logic import completion_tool_calls
from ar_domain.runs.logic import tools_not_supported
from ar_domain.tools.chat_loop import _answer, guard_unbacked, openai_tools, planned_from_model


def test_schema_default_still_has_no_tools() -> None:
    definition = assistant_definition()
    assert definition["tools"] == []
    assert not tools_not_supported(definition)


def test_an_old_assistant_gains_tools() -> None:
    service = ChatService()
    agent = next(row for row in service.agents.values() if row.get("slug") == "assistant")
    version = service.versions[agent["published_version_id"]]
    version["definition"] = assistant_definition()
    enable_assistant_tools(service)
    definition = service.versions[agent["published_version_id"]]["definition"]
    assert isinstance(definition, dict)
    assert definition["budget"]["max_tool_calls"] == 8
    enable_assistant_tools(object())


def test_published_assistant_can_call_tools() -> None:
    service = ChatService()
    agent = next(row for row in service.agents.values() if row.get("slug") == "assistant")
    version = service.versions[agent["published_version_id"]]
    definition = version["definition"]
    assert isinstance(definition, dict)
    servers = [item.get("server") for item in definition["tools"] if isinstance(item, dict)]
    assert "tickets" in servers
    assert definition["budget"]["max_tool_calls"] == 8
    enable_assistant_tools(service)
    assert service.versions[agent["published_version_id"]]["definition"] is definition


@pytest.mark.asyncio
async def test_a_blank_definition_does_not_plan_a_tool() -> None:
    from ar_domain.tools.chat_loop import maybe_tools

    service = ChatService()
    tenant, user = demo_id("tenant"), demo_id("admin")
    agent = next(row for row in service.agents.values() if row.get("slug") == "assistant")
    version = service.versions[agent["published_version_id"]]
    version["definition"] = "plain"
    conversation = service.create_conversation(tenant, user, agent["id"])
    posted = service.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "File a ticket: printer",
        schedule=False,
    )
    run = service.runs[uuid.UUID(str(posted["run"]["id"]))]
    assistant = service.messages[uuid.UUID(str(run["assistant_message_id"]))]
    assert await maybe_tools(service, run, assistant, "File a ticket: printer") is False


def test_tool_answer_hides_the_slash_command() -> None:
    assert _answer("/tool tickets.create_ticket", ["TCK-1"]) == "TCK-1"
    assert _answer("hello", []) == "I could not run that tool."


def test_unbacked_claim_is_replaced() -> None:
    claim = "I filed a ticket for the lobby printer."
    assert guard_unbacked(claim, recorded=False) == (
        "That action was not completed. No tool call was recorded."
    )
    assert guard_unbacked(claim, recorded=True) == claim
    assert guard_unbacked("A control test checks that a control works.", recorded=False).startswith(
        "A control"
    )


def test_tool_calls_are_read_from_the_message_or_a_qwen_block() -> None:
    assert completion_tool_calls({"choices": []}) == []
    assert completion_tool_calls({"choices": [{"message": {"content": "hello"}}]}) == []
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "petstore__create_pet",
                                "arguments": '{"body": {"name": "Mallow"}}',
                            }
                        }
                    ],
                }
            }
        ]
    }
    calls = completion_tool_calls(payload)
    assert calls == [{"name": "petstore__create_pet", "arguments": {"body": {"name": "Mallow"}}}]
    block = {
        "choices": [
            {
                "message": {
                    "content": (
                        '<tool_call>{"name": "tickets__create_ticket", '
                        '"arguments": {"title": "Jam"}}</tool_call>'
                    )
                }
            }
        ]
    }
    assert completion_tool_calls(block)[0]["name"] == "tickets__create_ticket"


def test_parser_skips_shapes_that_are_not_calls() -> None:
    assert completion_tool_calls(None) == []
    assert completion_tool_calls({"choices": [{"message": "nope"}]}) == []
    skipped = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        "nope",
                        {"function": "x"},
                        {"function": {"name": "", "arguments": "not-json"}},
                        {"function": {"name": "kept", "arguments": "not-json"}},
                    ],
                    "content": (
                        "<tool_call>not-json</tool_call>"
                        '<tool_call>[]</tool_call>'
                        '<tool_call>{"name": ""}</tool_call>'
                    ),
                }
            }
        ]
    }
    assert completion_tool_calls(skipped) == [{"name": "kept", "arguments": {}}]


def test_openai_tools_fill_an_empty_schema() -> None:
    tools = openai_tools(
        [
            {"model_name": "", "parameters": {}, "qualified_name": "tickets.create_ticket"},
            {
                "model_name": "petstore__create_pet",
                "parameters": {},
                "qualified_name": "petstore.create_pet",
                "description": "Create",
            },
        ]
    )
    assert len(tools) == 1
    function = tools[0]["function"]
    assert isinstance(function, dict)
    assert function["parameters"] == {"type": "object", "properties": {}}
    assert "body" in str(function["description"])


def test_model_names_map_onto_the_catalogue() -> None:
    tool_id = uuid.uuid4()
    catalog = [
        {
            "model_name": "petstore__create_pet",
            "tool_version_id": str(tool_id),
            "qualified_name": "petstore.create_pet",
            "risk_class": "W2",
        }
    ]
    planned = planned_from_model(
        catalog, [{"name": "petstore__create_pet", "arguments": {"body": {"name": "Mallow"}}}]
    )
    assert planned[0]["tool_version_id"] == tool_id
    assert planned[0]["risk_class"] == "W2"
    assert planned_from_model(catalog, [{"name": "unknown", "arguments": {}}]) == []


def test_remap_rewrites_the_store_grant() -> None:
    demo_user = demo_id("admin")
    bound_user = uuid.uuid4()
    grant_id = uuid.uuid4()
    store = ChatService()
    store.credential_grants[grant_id] = {
        "id": grant_id,
        "user_id": demo_user,
        "tenant_id": demo_id("tenant"),
        "provider_id": uuid.uuid4(),
        "status": "active",
    }
    _remap(store, {demo_user: bound_user})
    assert store.credential_grants[grant_id]["user_id"] == bound_user


@pytest.mark.asyncio
async def test_a_model_tool_call_waits_for_approval(monkeypatch: pytest.MonkeyPatch) -> None:
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

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "I created a pet named Mallow.",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "petstore__create_pet",
                                        "arguments": {"body": {"name": "Mallow"}},
                                    }
                                }
                            ],
                        }
                    }
                ]
            }

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
            assert "tools" in json
            assert "sk-cert-secret" not in str(headers)
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    agent_id = next(
        item_id
        for item_id, row in service.agents.items()
        if row.get("slug") == "assistant" and row.get("tenant_id") == tenant
    )
    conversation = service.create_conversation(tenant, user, agent_id)
    posted = service.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "Create a pet named Mallow",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await service.generate(run_id, "Create a pet named Mallow", [])
    assert service.runs[run_id]["status"] == "waiting_approval"
    assert "No tool call was recorded" not in str(service.runs[run_id].get("result_summary") or "")


@pytest.mark.asyncio
async def test_a_claim_without_a_tool_call_is_not_shown_as_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "I filed a ticket for the printer."}}]}

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> _Response:
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    agent_id = next(
        item_id
        for item_id, row in service.agents.items()
        if row.get("slug") == "assistant" and row.get("tenant_id") == tenant
    )
    conversation = service.create_conversation(tenant, user, agent_id)
    posted = service.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "File a ticket: printer", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await service.generate(run_id, "File a ticket: printer", [])
    assert service.runs[run_id]["result_summary"] == (
        "That action was not completed. No tool call was recorded."
    )


@pytest.mark.asyncio
async def test_ask_me_waits_for_input() -> None:
    service = ChatService()
    tenant, user = demo_id("tenant"), demo_id("admin")
    agent_id = next(
        item_id
        for item_id, row in service.agents.items()
        if row.get("slug") == "assistant" and row.get("tenant_id") == tenant
    )
    conversation = service.create_conversation(tenant, user, agent_id)
    posted = service.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Please ask me", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await service.generate(run_id, "Please ask me", [])
    assert service.runs[run_id]["status"] == "waiting_input"


@pytest.mark.asyncio
async def test_remote_turn_reports_provider_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatService(allow_loopback=True)

    class _Response:
        def __init__(self, status: int, payload: dict[str, object]) -> None:
            self.status_code = status
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> _Response:
            mode = _Client.mode
            if mode == "down":
                raise httpx.ConnectError("down")
            if mode == "status":
                return _Response(502, {})
            return _Response(200, {"choices": [{"message": {"content": ""}}]})

    _Client.mode = "status"
    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    async def turn(system: str, model: str) -> tuple[str, list[dict[str, object]]]:
        return await service._remote_turn(
            "hi", system, model=model, headers=None, timeout_s=1, tools=[]
        )

    text, calls = await turn("", "other")
    assert text == "The model provider returned an error."
    assert calls == []
    _Client.mode = "down"
    text, calls = await turn("", "other")
    assert text == "The model provider did not answer."
    _Client.mode = "empty"
    text, calls = await turn("system", "Qwen/Qwen3-32B")
    assert text == "The model provider returned an empty answer."


@pytest.mark.asyncio
async def test_an_unknown_tool_name_is_not_treated_as_done(monkeypatch: pytest.MonkeyPatch) -> None:
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

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {"function": {"name": "missing__tool", "arguments": {}}}
                            ],
                        }
                    }
                ]
            }

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> _Response:
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    agent_id = next(
        item_id
        for item_id, row in service.agents.items()
        if row.get("slug") == "assistant" and row.get("tenant_id") == tenant
    )
    conversation = service.create_conversation(tenant, user, agent_id)
    posted = service.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Do a thing", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await service.generate(run_id, "Do a thing", ["notes.txt"])
    summary = str(service.runs[run_id]["result_summary"])
    assert summary.startswith("Attached notes.txt.")
    assert "cannot run" in summary
