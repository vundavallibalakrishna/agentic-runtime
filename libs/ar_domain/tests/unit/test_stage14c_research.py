"""Research survives a reload, on any worker. Proof: unit."""

import asyncio
import uuid
from datetime import timedelta
from types import SimpleNamespace

from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.durable.hydrate import _load
from ar_domain.durable.tracking import TrackedDict
from ar_domain.research.driver import exhaust, store_results
from ar_domain.research.engine import (
    initial_state,
    max_steps,
    over_budget,
    pending_subtasks,
    state_of,
)
from ar_testing.demo import demo_store


def _runs() -> tuple[SimpleNamespace, TrackedDict]:
    store = SimpleNamespace(reloading=False)
    runs = TrackedDict(store, "runs")
    store.runs = runs
    return store, runs


def test_a_nested_write_after_a_reload_marks_the_run_dirty() -> None:
    store, runs = _runs()
    run_id = uuid.uuid4()
    runs[run_id] = {"id": run_id, "status": "running", "checkpoint": None}
    runs.dirty.clear()
    state = initial_state("kites")
    state["queries"] = [{"id": "1", "text": "kites", "status": "pending"}]
    _load(store, runs, run_id, {"status": "running", "checkpoint": {"research": state}})
    assert run_id not in runs.dirty

    run = runs[run_id]
    store_results(run, {"1": {"query_id": "1", "sources": [], "status": "done"}})

    assert run_id in runs.dirty
    assert pending_subtasks(state_of(run, "kites")) == []


def test_row_update_wraps_and_marks_like_an_assignment() -> None:
    _store, runs = _runs()
    run_id = uuid.uuid4()
    runs[run_id] = {"id": run_id}
    runs.dirty.clear()
    runs[run_id].update({"checkpoint": {"research": {"subtasks": {}}}})
    assert run_id in runs.dirty
    runs.dirty.clear()
    runs[run_id]["checkpoint"]["research"]["subtasks"]["1"] = {"status": "done"}
    assert run_id in runs.dirty
    runs.dirty.clear()
    runs[run_id]["checkpoint"].setdefault("extra", {})["a"] = 1
    assert run_id in runs.dirty
    runs.dirty.clear()
    assert runs[run_id].pop("missing", None) is None
    assert run_id not in runs.dirty
    runs[run_id].pop("checkpoint")
    assert run_id in runs.dirty


def test_a_failed_subtask_stays_pending() -> None:
    state = initial_state("kites")
    state["queries"] = [{"id": "1", "text": "kites", "status": "pending"}]
    run: dict[str, object] = {"checkpoint": {"research": state}}
    store_results(run, {"1": {"status": "failed"}})
    assert [row["id"] for row in pending_subtasks(state_of(run, "kites"))] == ["1"]


def test_the_wall_clock_limit_reads_the_stored_start() -> None:
    state = initial_state("kites")
    assert over_budget(state) is None
    state["started_at"] = (utcnow() - timedelta(seconds=500)).isoformat()
    assert over_budget(state) == "max_wall_clock_s"
    assert "started_monotonic" not in state
    assert max_steps(state) == 16


def test_research_is_known_from_the_stored_trigger() -> None:
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
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    assert run["trigger"] == "research"
    assert "mode" not in run
    payload = store._workflow_input(run, run["id"], "kites")
    assert payload["max_steps"] == 16
    asyncio.run(store.generate(run["id"], "What do the stored notes say about a kite?", []))
    assert run["status"] == "completed"


def test_running_out_of_steps_ends_the_run_failed() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "kites", research=True, schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    exhaust(store, run)
    assert run["status"] == "failed"
    assert run["error"]["code"] == "budget_exceeded"
    assert run["error"]["reason"] == "max_steps"
    failed = [row for row in store.audit_log if row.get("action") == "research.failed"]
    assert failed and failed[0]["outcome"] == "failure"
    exhaust(store, run)
    assert len([row for row in store.audit_log if row.get("action") == "research.failed"]) == 1


def test_a_replayed_search_is_not_recorded_as_a_finished_subtask(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from ar_domain.research import gateway

    monkeypatch.setattr(gateway, "_version_id", lambda _store, _name: uuid.uuid4())
    monkeypatch.setattr(
        gateway, "execute_tool", lambda _store, _request: {"status": "succeeded", "replayed": True}
    )
    result = gateway.subtask_via_gateway(object(), {"id": uuid.uuid4()}, {"id": "1", "text": "k"})
    assert result["status"] == "failed"
    state = initial_state("kites")
    state["queries"] = [{"id": "1", "text": "k", "status": "pending"}]
    run: dict[str, object] = {"checkpoint": {"research": state}}
    store_results(run, {"1": result})
    assert pending_subtasks(state_of(run, "kites"))


def test_a_production_store_gets_shared_state_where_it_is_built(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", "http://sandbox-manager:8003")
    """Every process builds its store the same way, so none can forget the Valkey books."""
    from ar_common.settings import BaseServiceSettings, EnvName
    from ar_domain import process_state
    from ar_domain.readmodel import boot

    attached: list[object] = []
    monkeypatch.setattr(
        process_state, "install_shared_state", lambda store, _s: attached.append(store)
    )
    monkeypatch.setenv("AR_CURSOR_SECRET", "not-the-dev-default")
    settings = BaseServiceSettings(env=EnvName.STAGING, service_name="mcp-gateway")
    store = boot.build_product_store(settings)
    assert attached == [store]
    attached.clear()
    boot.build_product_store(BaseServiceSettings(env=EnvName.DEV, service_name="mcp-gateway"))
    assert attached == []


def test_what_a_turn_was_asked_is_stored_on_the_run() -> None:
    from ar_domain.runs.request import ask, asked

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    schema = {"type": "object", "properties": {"capital": {"type": "string"}}}
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "What is the capital of France?",
        schedule=False,
        response_format=schema,
        suggest_followups=True,
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    assert run["request"] == {"suggest_followups": True, "response_format": schema}
    assert "response_format" not in run
    # A worker sees only what the database row holds.
    reloaded: dict[str, object] = {"id": run["id"], "request": dict(run["request"])}
    assert asked(reloaded, "response_format") == schema
    assert asked(reloaded, "suggest_followups") is True
    assert asked({"id": run["id"]}, "response_format") is None
    try:
        ask(reloaded, "mode", "research")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown option was accepted")


def test_a_row_filled_in_after_it_is_stored_keeps_those_writes() -> None:
    from ar_domain.durable.tracking import keep

    _store, documents = _runs()
    document_id = uuid.uuid4()
    built = {"id": document_id, "status": "pending", "size_bytes": 0}
    row = keep(documents, document_id, built)
    documents.dirty.clear()
    row["status"] = "indexed"
    assert documents[document_id]["status"] == "indexed"
    assert document_id in documents.dirty
    # A plain bucket hands back the same dict it was given.
    plain: dict[object, object] = {}
    assert keep(plain, document_id, built) is built


def test_research_bounds_and_state_start_from_an_empty_run() -> None:
    from ar_domain.research.engine import initial_state, save_state, state_of

    limited = initial_state("kites", {"max_steps": 3, "max_sources": True, "unknown": 9})
    plain = initial_state("kites")
    # A caller's limit replaces the default. A value that is not a count is ignored.
    assert limited != plain
    run: dict[str, object] = {}
    state = state_of(run, "kites")
    assert state["question"] == "kites"
    assert state_of(run, "something else") is state
    other: dict[str, object] = {"checkpoint": "broken"}
    save_state(other, {"question": "kept"})
    assert other["checkpoint"] == {"research": {"question": "kept"}}


def test_a_page_that_cannot_be_fetched_says_why() -> None:
    import httpx

    from ar_domain.research.fetch import fetch_page

    store = demo_store()

    def down(*_a: object, **_k: object) -> object:
        raise httpx.ConnectError("no route")

    store.http_send = down
    store.egress_allowlist = ["*"]
    # A private address is refused before anything is sent.
    denied = fetch_page(store, "http://127.0.0.1/note")
    assert denied["error"] == "egress_denied"
    assert fetch_page(store, "https://example.com/note")["error"] == "upstream_error"
    store.http_send = lambda *_a, **_k: httpx.Response(503, text="busy")
    failed = fetch_page(store, "https://example.com/note")
    assert failed["error"] == "upstream_error"
    assert failed["message"] == "HTTP 503"


def test_a_search_provider_keeps_its_key_out_of_results(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import httpx
    import pytest

    from ar_domain.tools import searching
    from ar_domain.tools.searching import SearchRejectedError, TavilySearch

    answers = [
        httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Kites", "url": "https://example.com/k?key=sekret", "content": "x"},
                    "not a row",
                    {"title": "", "url": ""},
                ]
            },
        ),
        httpx.Response(401, text="no"),
        httpx.Response(500, text="down"),
        httpx.Response(200, json=["not an object"]),
    ]
    monkeypatch.setattr(searching.httpx, "post", lambda *_a, **_k: answers.pop(0))
    provider = TavilySearch("sekret")
    rows = provider.search("kites", limit=50)
    assert len(rows) == 1
    assert "sekret" not in rows[0]["url"]
    with pytest.raises(SearchRejectedError):
        provider.search("kites", limit=1)
    with pytest.raises(httpx.HTTPError):
        provider.search("kites", limit=1)
    assert provider.search("kites", limit=1) == []
