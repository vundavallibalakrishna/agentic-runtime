"""Real-model proof for one batch-two connector.

The model key is read from AR_CERT_LLM_API_KEY and is never printed.
ServiceNow is not called. The connector talks to a local replay of a
recorded Table API response. The evidence file says so.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import orjson

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18140")
REPLAY_PORT = int(os.environ.get("AR_PROOF_REPLAY_PORT", "18142"))
OUT = Path(os.environ.get("AR_PROOF_OUT", "/tmp/m27-proof"))  # noqa: S108
_INCIDENT = (
    b'{"result":{"sys_id":"abc","number":"INC0009001",'
    b'"short_description":"Cannot reach the mail gateway"}}'
)


class _Replay(BaseHTTPRequestHandler):
    """Recorded ServiceNow responses. This process is not ServiceNow."""

    def do_GET(self) -> None:
        if self.path.startswith("/api/now/table/incident/abc"):
            self._send(200, _INCIDENT)
            return
        if self.path.startswith("/api/now/table/incident/missing"):
            self._send(404, b'{"error":{"message":"No Record found"}}')
            return
        if self.path.startswith("/api/now/table/incident/limited"):
            self._send(429, b"{}", retry_after="15")
            return
        self._send(200, b'{"result":[]}')

    def do_POST(self) -> None:
        self._send(429, b"{}", retry_after="15")

    def _send(self, status: int, body: bytes, retry_after: str = "") -> None:
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        if retry_after:
            self.send_header("retry-after", retry_after)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def _scrub(text: str) -> str:
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
        text = text.replace(secret, "[redacted]")
    return text


def _client() -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=180.0)
    response = client.post("/api/v1/auth/dev-login", params={"email": "admin@dev.local"})
    if response.status_code not in {200, 302, 303}:
        raise SystemExit(f"dev login failed: {response.status_code}")
    token = client.cookies.get("ar_csrf")
    if not token:
        raise SystemExit("dev login did not set a CSRF cookie")
    client.headers["x-csrf-token"] = token
    return client


def _json(response: httpx.Response) -> dict[str, object]:
    text = _scrub(response.text)
    if response.status_code >= 300:
        raise SystemExit(f"{response.request.method} {response.status_code} {text[:500]}")
    body = response.json()
    if not isinstance(body, dict):
        raise SystemExit("response was not an object")
    return body


def _items(client: httpx.Client, path: str) -> list[dict[str, object]]:
    rows = _json(client.get(path)).get("items")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _tool_id(client: httpx.Client, name: str) -> str:
    for row in _items(client, "/api/v1/tools"):
        if row.get("qualifiedName") == f"connectors.{name}":
            return str(row["toolId"])
    raise SystemExit(f"missing tool {name}")


def _call(client: httpx.Client, name: str, arguments: dict[str, object]) -> dict[str, object]:
    result = _json(
        client.post(f"/api/v1/tools/{_tool_id(client, name)}:test", json={"arguments": arguments})
    )
    return orjson.loads(_scrub(json.dumps(result)))


def _setup_model(client: httpx.Client) -> None:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("AR_CERT_LLM_API_KEY is missing")
    if any(row.get("alias") == "qwenm27" for row in _items(client, "/api/v1/model-aliases")):
        return
    provider = _json(
        client.post(
            "/api/v1/model-providers",
            json={
                "name": "DeepInfra M27",
                "kind": "openai_compatible",
                "baseUrl": "https://api.deepinfra.com/v1/openai",
                "apiKey": key,
            },
        )
    )
    if key in json.dumps(provider):
        raise SystemExit("provider response exposed the API key")
    chat = _json(
        client.post(
            "/api/v1/models",
            json={
                "providerId": provider["id"],
                "name": "Qwen3 32B",
                "upstreamModel": "Qwen/Qwen3-32B",
                "kind": "chat",
            },
        )
    )
    _json(
        client.post(
            "/api/v1/model-aliases",
            json={"alias": "qwenm27", "kind": "chat", "primaryModelId": chat["id"]},
        )
    )
    tested = _json(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
    if not tested.get("ok"):
        raise SystemExit("provider test failed")


def _ask(client: httpx.Client) -> dict[str, object]:
    agent = _json(
        client.post(
            "/api/v1/agents",
            json={
                "slug": f"m27-{int(time.time())}",
                "name": "Incident reader",
                "visibility": "private",
                "definition": {
                    "instructions": (
                        "When asked for an incident, call servicenow_get_incident "
                        "and quote the incident number from the tool result. "
                        "Do not invent the number. Say that the tool result is a replay "
                        "if the result says so."
                    ),
                    "model": {"alias": "qwenm27"},
                    "tools": [
                        {
                            "server": "connectors",
                            "version": "*",
                            "include": ["servicenow_get_incident"],
                        }
                    ],
                    "budget": {
                        "maxSteps": 6,
                        "maxToolCalls": 3,
                        "maxWallClockS": 180,
                        "maxCostMicros": 5_000_000,
                        "maxTokens": 8000,
                    },
                },
            },
        )
    )
    _json(client.post(f"/api/v1/agents/{agent['id']}:publish", json={"changeNote": "proof"}))
    conversation = _json(
        client.post(
            "/api/v1/conversations",
            json={"agentId": agent["id"], "modelAlias": "qwenm27"},
        )
    )
    posted = _json(
        client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={
                "text": (
                    "Read ServiceNow incident abc with servicenow_get_incident. "
                    "Quote the incident number."
                )
            },
        )
    )
    run = posted.get("run")
    if not isinstance(run, dict):
        raise SystemExit("message did not start a run")
    run_id = str(run["id"])
    deadline = time.monotonic() + 180
    status = ""
    summary = ""
    while time.monotonic() < deadline:
        current = _json(client.get(f"/api/v1/runs/{run_id}"))
        status = str(current.get("status") or "")
        summary = _scrub(str(current.get("resultSummary") or ""))
        if status in {"completed", "failed", "waiting_approval", "budget_exceeded", "cancelled"}:
            break
        time.sleep(2)
    calls = _scrub(client.get(f"/api/v1/runs/{run_id}/tool-calls").text)
    return {"status": status, "summary": summary[:1000], "calls": calls[:2000]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", REPLAY_PORT), _Replay)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = _client()
    _setup_model(client)
    _json(
        client.post(
            "/api/v1/connectors/servicenow:install",
            json={
                "connectionName": "snow-replay",
                "kind": "basic",
                "username": "ada",
                "secret": "replay-secret",
                "config": {"baseUrl": f"http://127.0.0.1:{REPLAY_PORT}"},
            },
        )
    )
    read = _call(client, "servicenow_get_incident", {"sys_id": "abc"})
    missing = _call(client, "servicenow_get_incident", {"sys_id": "missing"})
    limited = _call(client, "servicenow_get_incident", {"sys_id": "limited"})
    evidence = {
        "label": "recorded-response replay, not a live ServiceNow call",
        "replay": f"http://127.0.0.1:{REPLAY_PORT}",
        "read": {
            "status": read.get("status"),
            "text": str(read.get("text") or "")[:400],
        },
        "missing": {
            "status": missing.get("status"),
            "text": str(missing.get("text") or missing.get("error") or "")[:300],
        },
        "limited": {
            "status": limited.get("status"),
            "text": str(limited.get("text") or limited.get("error") or "")[:300],
        },
        "chat": _ask(client),
    }
    text = _scrub(json.dumps(evidence, indent=2))
    if "INC0009001" not in text:
        raise SystemExit("replay incident number was not returned")
    (OUT / "evidence.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
