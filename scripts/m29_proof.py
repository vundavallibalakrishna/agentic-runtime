"""Live proof that a published agent is reachable from outside.

The model key is read from AR_CERT_LLM_API_KEY and is never printed.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import orjson

if TYPE_CHECKING:
    from typing import Any

import httpx

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18129")
ALIAS = "qwenm29"
PEER_PORT = 18130


def _scrub(text: str) -> str:
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
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


def _json(response: httpx.Response) -> dict[str, Any]:
    text = _scrub(response.text)
    if response.status_code >= 300:
        raise SystemExit(f"{response.request.method} {response.status_code} {text[:800]}")
    body = response.json()
    if not isinstance(body, dict):
        raise SystemExit("response was not an object")
    return body


def _items(client: httpx.Client, path: str) -> list[dict[str, Any]]:
    payload = _json(client.get(path))
    rows = payload.get("items")
    if rows is None:
        rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _setup_model(client: httpx.Client) -> None:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("AR_CERT_LLM_API_KEY is missing")
    if any(row.get("alias") == ALIAS for row in _items(client, "/api/v1/model-aliases")):
        return
    provider = _json(
        client.post(
            "/api/v1/model-providers",
            json={
                "name": "DeepInfra M29",
                "kind": "openai_compatible",
                "baseUrl": "https://api.deepinfra.com/v1/openai",
                "apiKey": key,
            },
        )
    )
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
            json={"alias": ALIAS, "kind": "chat", "primaryModelId": chat["id"]},
        )
    )
    tested = _json(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
    if not tested.get("ok"):
        raise SystemExit("provider test failed")


def _publish(client: httpx.Client) -> str:
    slug = "m29-exposed"
    existing = [row for row in _items(client, "/api/v1/agents") if row.get("slug") == slug]
    if existing:
        return str(existing[0]["id"])
    agent = _json(
        client.post(
            "/api/v1/agents",
            json={
                "slug": slug,
                "name": "Exposed",
                "visibility": "private",
                "definition": {
                    "persona": {"displayName": "Exposed"},
                    "instructions": (
                        "Answer in one short sentence. If asked for a number, give only the number."
                    ),
                    "model": {"alias": ALIAS},
                    "tools": [
                        {
                            "server": "control",
                            "version": "*",
                            "include": ["propose_change", "a2a_call"],
                        }
                    ],
                    "budget": {
                        "maxSteps": 4,
                        "maxToolCalls": 2,
                        "maxWallClockS": 120,
                        "maxCostMicros": 2_000_000,
                        "maxTokens": 4000,
                    },
                },
            },
        )
    )
    _json(client.post(f"/api/v1/agents/{agent['id']}:publish", json={"changeNote": "proof"}))
    return str(agent["id"])


def _external(client: httpx.Client, secret: str) -> httpx.Client:
    external = httpx.Client(base_url=BASE, timeout=180.0)
    external.headers["Authorization"] = f"Bearer {secret}"
    del client
    return external


def _ask_model(message: str) -> str:
    """One short completion. The key stays in the request and is not logged."""
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    response = httpx.post(
        "https://api.deepinfra.com/v1/openai/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "Qwen/Qwen3-32B",
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 64,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=90,
    )
    response.raise_for_status()
    body = response.json()
    return str(body["choices"][0]["message"]["content"]).strip()


def _start_peer() -> None:
    """A separate A2A process-thread. It does not call back into the API."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not self.path.endswith("agent-card.json"):
                self.send_response(404)
                self.end_headers()
                return
            card = {
                "name": "Remote",
                "url": f"http://127.0.0.1:{PEER_PORT}/a2a",
                "version": "1",
            }
            payload = json.dumps(card).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:
            length = int(self.headers.get("content-length") or "0")
            raw = self.rfile.read(length)
            if not self.headers.get("authorization"):
                self.send_response(401)
                self.end_headers()
                return
            try:
                body = orjson.loads(raw)
                message = body["params"]["message"]["parts"][0]["text"]
                answer = _ask_model(str(message))
            except Exception:  # noqa: BLE001 — the peer returns a task error, not a traceback
                answer = ""
            task = {
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "status": {"state": "completed" if answer else "failed"},
                    "artifacts": [{"parts": [{"kind": "text", "text": answer}]}],
                },
            }
            payload = json.dumps(task).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args: object) -> None:
            del fmt, args

    server = ThreadingHTTPServer(("127.0.0.1", PEER_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _artifact(result: dict[str, Any]) -> str:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        return ""
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        parts = artifact.get("parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], dict):
            return str(parts[0].get("text") or "").strip()
    return ""


def main() -> None:
    _start_peer()
    client = _client()
    _setup_model(client)
    agent_id = _publish(client)
    created = _json(
        client.post(
            f"/api/v1/agents/{agent_id}/api-keys",
            json={"label": "Proof", "rateLimitRpm": 30, "monthlyQuota": 100},
        )
    )
    secret = str(created["key"])
    external = _external(client, secret)
    bare = httpx.Client(base_url=BASE, timeout=30.0)
    refused = bare.post("/v1/agents/m29-exposed/conversations")
    conversation = _json(external.post("/v1/agents/m29-exposed/conversations"))
    idem = str(uuid.uuid4())
    body = {"text": "What is 2 + 2? Reply with only the number."}
    first = _json(
        external.post(
            f"/v1/agents/m29-exposed/conversations/{conversation['id']}/messages",
            headers={"Idempotency-Key": idem},
            json=body,
        )
    )
    second = external.post(
        f"/v1/agents/m29-exposed/conversations/{conversation['id']}/messages",
        headers={"Idempotency-Key": idem},
        json=body,
    )
    streamed = external.post(
        f"/v1/agents/m29-exposed/conversations/{conversation['id']}/messages",
        json={"text": "Name the integer that comes after 4. One word.", "stream": True},
    )
    card = _json(external.get("/v1/agents/m29-exposed/.well-known/agent-card.json"))
    task = _json(
        external.post(
            "/v1/agents/m29-exposed/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "task-1",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [
                            {"kind": "text", "text": "What is 3 + 3? Reply with only the number."}
                        ],
                    }
                },
            },
        )
    )
    listed = _json(
        external.post(
            "/v1/mcp",
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    )
    called = _json(
        external.post(
            "/v1/mcp",
            headers={"Accept": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "agent_m29_exposed",
                    "arguments": {"message": "What is 5 + 5? Reply with only the number."},
                },
            },
        )
    )
    write = _json(
        external.post(
            "/v1/mcp",
            headers={"Accept": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "agent_m29_exposed",
                    "arguments": {
                        "write": {
                            "tool": "control.propose_change",
                            "arguments": {"summary": "rename the record"},
                        }
                    },
                },
            },
        )
    )
    tight = _json(
        client.post(
            f"/api/v1/agents/{agent_id}/api-keys",
            json={"label": "Tight", "rateLimitRpm": 2, "monthlyQuota": 10},
        )
    )
    tight_client = _external(client, str(tight["key"]))
    statuses = [tight_client.get("/.well-known/agent-card.json").status_code for _ in range(3)]
    _json(client.delete(f"/api/v1/agents/{agent_id}/api-keys/{created['id']}"))
    revoked = external.post("/v1/agents/m29-exposed/conversations")
    remote_key = _json(
        client.post(
            f"/api/v1/agents/{agent_id}/api-keys",
            json={"label": "Remote", "rateLimitRpm": 30, "monthlyQuota": 20},
        )
    )
    _json(
        client.post(
            "/api/v1/secrets",
            json={"name": "m29-remote", "kind": "generic", "value": str(remote_key["key"])},
        )
    )
    tools = _items(client, "/api/v1/tools")
    remote_tool = next(row for row in tools if row.get("qualifiedName") == "control.a2a_call")
    tool_id = remote_tool.get("toolId") or remote_tool.get("id")
    remote = _json(
        client.post(
            f"/api/v1/tools/{tool_id}:test",
            json={
                "arguments": {
                    "url": f"http://127.0.0.1:{PEER_PORT}/.well-known/agent-card.json",
                    "message": "What is 6 + 6? Reply with only the number.",
                    "secret_name": "m29-remote",
                }
            },
        )
    )
    evidence = {
        "missing": refused.status_code,
        "sync": {"output": first.get("output"), "status": first.get("status")},
        "replay": {
            "runId": second.json().get("id"),
            "same": second.json().get("id") == first.get("id"),
            "header": second.headers.get("idempotent-replayed"),
        },
        "stream": streamed.status_code,
        "streamHasData": "data:" in streamed.text,
        "card": card.get("url"),
        "taskState": (task.get("result") or {}).get("status", {}).get("state")
        if isinstance(task.get("result"), dict)
        else None,
        "taskText": _artifact(task.get("result") if isinstance(task.get("result"), dict) else {}),
        "mcpTools": [
            item.get("name")
            for item in (listed.get("result") or {}).get("tools", [])
            if isinstance(item, dict)
        ]
        if isinstance(listed.get("result"), dict)
        else [],
        "mcpCall": (called.get("result") or {}).get("content")
        if isinstance(called.get("result"), dict)
        else None,
        "approval": (write.get("result") or {}).get("structuredContent")
        if isinstance(write.get("result"), dict)
        else None,
        "rate": statuses,
        "revoked": revoked.status_code,
        "remote": {
            "isError": remote.get("isError"),
            "text": str(remote.get("resultPreview") or remote.get("text") or "")[:200],
        },
    }
    text = _scrub(json.dumps(evidence, indent=2))
    if secret and secret in text:
        text = text.replace(secret, "[redacted]")
    for hidden in (str(tight.get("key") or ""), str(remote_key.get("key") or "")):
        if hidden:
            text = text.replace(hidden, "[redacted]")
    print(text)
    if refused.status_code != 401 or revoked.status_code != 401:
        raise SystemExit("auth checks failed")
    if not evidence["replay"]["same"]:
        raise SystemExit("idempotent retry did not return the same run")
    if statuses[-1] != 429:
        raise SystemExit(f"rate limit did not trip: {statuses}")
    if "12" not in str(evidence["remote"]["text"]):
        raise SystemExit("remote A2A tool did not return the model answer")
    if "6" not in str(evidence["taskText"]):
        raise SystemExit("A2A task did not return the model answer")


if __name__ == "__main__":
    main()
