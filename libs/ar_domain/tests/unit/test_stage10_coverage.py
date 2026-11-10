"""Cover the stage 10 paths the happy-path tests leave closed. Proof: unit."""

import asyncio
import uuid

import httpx

from ar_domain.chat.service import demo_id
from ar_domain.evals.harness import case_passed, summarise
from ar_domain.loop.planning import parse_plan
from ar_domain.loop.repair import acknowledges_failure, repair_prompt
from ar_domain.loop.routing import replace_routes, routed_completion
from ar_domain.research.driver import advance_research
from ar_domain.research.providers import search
from ar_domain.tools.named_secrets import write_named_secret
from ar_testing.demo import demo_store


def test_scores_cover_refusal_tool_and_citation() -> None:
    refused = case_passed(
        {
            "kind": "redteam",
            "expect": {"refuses": True, "contains": [], "tool": "", "cites": False},
        },
        {"text": "I can't help with that request.", "tool": ""},
    )
    cited = case_passed(
        {
            "kind": "assistant",
            "expect": {"refuses": False, "contains": ["note"], "tool": "files.list", "cites": True},
        },
        {"text": "A stored note [1]", "tool": "files.list"},
    )
    assert refused["pass"] and refused["refusal"]
    assert cited["pass"] and cited["citation"] and cited["tool"]
    summary = summarise([refused, cited])
    assert summary["pass_rate"] == 1


def test_plan_and_repair_edges() -> None:
    items, error = parse_plan('```json\n{"steps":[{"title":"Look"}]}\n```')
    assert error == "" and items and items[0]["id"] == "1"
    assert parse_plan("[]")[0] is None
    assert parse_plan('{"steps":["nope"]}')[0] is None
    assert "schema" in repair_prompt("schema", "missing query")
    assert acknowledges_failure("The tool was blocked.")


def test_routes_fall_through_on_5xx_and_bad_json() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    routes = [
        {"id": "down", "base_url": "https://down.example/v1", "model": "m", "secret_name": ""},
        {"id": "bad", "base_url": "https://bad.example/v1", "model": "m", "secret_name": ""},
        {"id": "ok", "base_url": "https://ok.example/v1", "model": "m", "secret_name": ""},
    ]
    replace_routes(store, tenant, routes)

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def post(
            self, url: str, json: object = None, headers: object = None
        ) -> httpx.Response:
            del json, headers
            if "down" in url:
                return httpx.Response(503, json={"error": "down"})
            if "bad" in url:
                return httpx.Response(200, text="not-json")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "ok",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "function": {"name": "files.list", "arguments": "{}"},
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1},
                },
            )

    original = httpx.AsyncClient
    httpx.AsyncClient = _Client  # type: ignore[misc, assignment]
    try:
        result = asyncio.run(
            routed_completion(
                store,
                [{"role": "user", "content": "hi"}],
                [],
                tenant_id=tenant,
                routes=routes,
            )
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc, assignment]
    assert result["endpoint_id"] == "ok"
    assert result["tool_calls"]


def test_search_providers_parse_their_payloads() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    write_named_secret(store, tenant, "search", "token")

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, kwargs
        if "searx" in url:
            return httpx.Response(
                200,
                json={"results": [{"title": "S", "url": "https://example.com/s", "content": "c"}]},
            )
        if "brave" in url:
            return httpx.Response(
                200,
                json={
                    "web": {
                        "results": [
                            {"title": "B", "url": "https://example.com/b", "description": "d"}
                        ]
                    }
                },
            )
        if "tavily" in url:
            return httpx.Response(
                200,
                json={"results": [{"title": "T", "url": "https://example.com/t", "content": "c"}]},
            )
        if "bing" in url:
            return httpx.Response(
                200,
                json={
                    "webPages": {
                        "value": [{"name": "N", "url": "https://example.com/n", "snippet": "s"}]
                    }
                },
            )
        return httpx.Response(500, text="no")

    store.http_send = send
    settings = store.tenant_settings.setdefault(tenant, {})
    for name, base in (
        ("searxng", "https://searx.example"),
        ("brave", ""),
        ("tavily", ""),
        ("bing", ""),
    ):
        settings["search"] = {"provider": name, "secret_name": "search", "base_url": base}
        hits = search(store, tenant, "kites", limit=2)
        assert hits and hits[0]["url"].startswith("https://")


def test_research_activity_advances_and_subtask_is_idempotent() -> None:
    from ar_runtime.activities.expire_approval import bind_store
    from ar_runtime.activities.research_step import research_cancel, research_step, research_subtask

    store = demo_store()
    bind_store(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "Notes about kites",
        research=True,
        schedule=False,
    )
    run_id = str(posted["run"]["id"])
    step = asyncio.run(research_step({"run_id": run_id, "text": "Notes about kites"}))
    assert step["kind"] == "fanout"
    subtasks = step["subtasks"]
    assert subtasks
    done = asyncio.run(research_subtask({"run_id": run_id, **subtasks[0]}))
    assert done["status"] == "done"
    again = asyncio.run(research_subtask({"run_id": run_id, **subtasks[0]}))
    assert again["status"] == "done"
    missing = asyncio.run(research_step({"run_id": str(uuid.uuid4()), "text": "x"}))
    assert missing["kind"] == "final"
    cancelled = asyncio.run(research_cancel({"run_id": run_id}))
    assert cancelled["status"] == "cancelled"


def test_handler_rejects_blank_arguments() -> None:
    from ar_domain.research.handlers import dispatch_context, dispatch_research

    store = demo_store()
    assert dispatch_research(store, "search", {})["code"] == "validation_failed"
    assert dispatch_research(store, "fetch", {"url": "notaurl"})["code"] == "validation_failed"
    assert dispatch_research(store, "missing", {})["code"] == "not_found"
    assert dispatch_context(store, "other", {})["code"] == "not_found"
    assert dispatch_context(store, "retrieve", {})["code"] == "validation_failed"


def test_one_research_step_returns_fanout() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "What do the stored notes say about a kite?",
        research=True,
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    kind = asyncio.run(
        advance_research(
            store, store.runs[run_id], "What do the stored notes say about a kite?", one_step=True
        )
    )
    assert kind == "fanout"
