"""Regressions for live certification run 4."""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from ar_common.egress_http import EgressDenied, http_post
from ar_common.internal_auth import sign_request
from ar_common.internal_http import internal_post
from ar_domain.knowledge.retrieval import _env_int
from ar_domain.sandboxes.browser import _gesture
from ar_domain.tools.gateway_client import execute_tool


def test_empty_rerank_candidate_env_keeps_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_KNOWLEDGE_RERANK_CANDIDATES", "")
    assert _env_int("AR_KNOWLEDGE_RERANK_CANDIDATES", 50) == 50


def test_external_egress_denies_a_private_service_and_cluster_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ar_common.egress_http.resolve_host", lambda _host: ["10.0.0.8"])
    with pytest.raises(EgressDenied, match=r"blocked|private"):
        http_post("http://mcp-gateway:8002/healthz", timeout=0.2)
    with pytest.raises(httpx.HTTPError) as caught:
        internal_post("http://mcp-gateway:8002/healthz", timeout=0.2)
    assert not isinstance(caught.value, EgressDenied)


def test_a_tool_call_reaches_the_gateway_and_names_the_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen["path"] = self.path
            seen["auth"] = self.headers.get("X-AR-Internal", "")
            body = b'{"status":"succeeded","result_preview":"listed"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _fmt: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.setenv("AR_MCP_GATEWAY_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("AR_INTERNAL_AUTH_SECRET", "install-secret")
    store = type("Store", (), {"tool_gateway_http": True, "tool_versions": {}})()
    try:
        result = execute_tool(store, {"tool_version_id": uuid.uuid4(), "arguments": {}})
    finally:
        server.shutdown()
    assert result["status"] == "succeeded"
    assert seen["path"] == "/internal/v1/tool-calls:execute"
    stamp, _, _digest = seen["auth"].partition(".")
    assert seen["auth"] == sign_request(
        "install-secret", "POST", "/internal/v1/tool-calls:execute", now=int(stamp)
    )

    def deny(_host: str) -> list[str]:
        return ["10.0.0.8"]

    monkeypatch.setattr("ar_common.egress_http.resolve_host", deny)


def test_click_without_a_target_is_refused() -> None:
    result = _gesture({}, {"browser_sessions": {}}, {}, "click", {})
    assert result["is_error"] is True
    assert result["text"] == "ref or text is required"


def test_run_events_page_serialises_uuids() -> None:
    """The JSON events page used to raise TypeError on a UUID."""
    import orjson

    from ar_common.json_api import camelize

    page = {
        "items": [{"id": uuid.uuid4(), "run_id": uuid.uuid4(), "type": "run.completed"}],
        "next_cursor": None,
        "has_more": False,
    }
    encoded = orjson.dumps(camelize(page))
    loaded = orjson.loads(encoded)
    assert loaded["items"][0]["runId"]
    with pytest.raises(TypeError):
        json.dumps(page)


def test_a_completed_run_is_not_marked_interrupted() -> None:
    from ar_domain.chat.service import demo_id
    from ar_domain.durable.hydrate import _load
    from ar_domain.durable.tracking import install_tracking
    from ar_testing.demo import demo_store

    store = demo_store()
    install_tracking(store)
    run_id = uuid.uuid4()
    store.runs[run_id] = {"id": run_id, "status": "running", "tenant_id": demo_id("tenant")}
    store.runs[run_id]["note"] = "dirty"
    _load(store, store.runs, run_id, {"id": run_id, "status": "completed"})
    assert store.runs[run_id]["status"] == "completed"
    store.mark_not_resumed(run_id)
    assert store.runs[run_id]["status"] == "completed"


def test_an_answer_is_folded_into_the_loop_for_the_model() -> None:
    from ar_domain.tools.resume import apply_decision
    from ar_domain.tools.worker_loop import read_worker_loop, write_worker_loop

    run = {
        "id": uuid.uuid4(),
        "status": "waiting_input",
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "checkpoint": {},
    }
    write_worker_loop(
        run,
        {
            "opened": True,
            "phase": "tools",
            "messages": [{"role": "assistant", "tool_calls": []}],
            "pending_calls": [{"id": "ask", "name": "agents_ask"}],
            "pending_index": 0,
        },
    )
    store = type("Store", (), {})()
    applied = apply_decision(store, run, {"status": "input", "text": "blue"})
    assert applied == "continue"
    state = read_worker_loop(run)
    assert isinstance(state, dict)
    assert state["phase"] == "model"
    assert run["status"] == "running"
    assert "The person answered: blue" in str(state["messages"][-1]["content"])
