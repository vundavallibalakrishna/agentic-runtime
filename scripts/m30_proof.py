"""Live M30 proof. The provider key is read from the environment and never stored."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import orjson
from sign_in import sign_in

if TYPE_CHECKING:
    from typing import Any

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18131")
ALIAS = "qwenm30"
DOCK = (
    "# North dock\n\nThe warehouse code for the north dock is ND-1844-QUILL. "
    "It is not written in any public standard.\n"
)
STANDARD = "The document must state the warehouse code for the north dock.\n"


def _scrub(text: str) -> str:
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _client() -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=180.0)
    client.cookies.update(sign_in(BASE, "admin@dev.local"))
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
    dumped = json.dumps(body)
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in dumped:
        raise SystemExit("a response contained the provider key")
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
                "name": "DeepInfra M30",
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
    embed = _json(
        client.post(
            "/api/v1/models",
            json={
                "providerId": provider["id"],
                "name": "bge-m3",
                "upstreamModel": "BAAI/bge-m3",
                "kind": "embedding",
            },
        )
    )
    _json(
        client.post(
            "/api/v1/model-aliases",
            json={"alias": ALIAS, "kind": "chat", "primaryModelId": chat["id"]},
        )
    )
    _json(
        client.post(
            "/api/v1/model-aliases",
            json={"alias": "bge-m3", "kind": "embedding", "primaryModelId": embed["id"]},
        )
    )
    tested = _json(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
    if not tested.get("ok"):
        raise SystemExit("provider test failed")


def _budget() -> dict[str, int]:
    return {
        "maxSteps": 6,
        "maxToolCalls": 4,
        "maxWallClockS": 180,
        "maxCostMicros": 5_000_000,
        "maxTokens": 8000,
    }


def _publish(client: httpx.Client, slug: str, name: str, definition: dict[str, Any]) -> str:
    agent = _json(
        client.post(
            "/api/v1/agents",
            json={"slug": slug, "name": name, "visibility": "private", "definition": definition},
        )
    )
    _json(
        client.post(
            f"/api/v1/agents/{agent['id']}:publish",
            json={"changeNote": "m30", "skipEvalGate": True},
        )
    )
    return str(agent["id"])


def _wait(client: httpx.Client, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 240
    current: dict[str, Any] = {}
    while time.monotonic() < deadline:
        current = _json(client.get(f"/api/v1/runs/{run_id}"))
        if str(current.get("status") or "") not in {"queued", "running"}:
            break
        time.sleep(2)
    conversation_id = str(current.get("conversationId") or "")
    text = ""
    if conversation_id:
        conversation = _json(client.get(f"/api/v1/conversations/{conversation_id}"))
        messages = conversation.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                text = str(last.get("text") or last.get("content") or "")
    return {
        "status": current.get("status"),
        "summary": _scrub(str(current.get("resultSummary") or ""))[:500],
        "text": _scrub(text)[:500],
        "runId": run_id,
    }


def _chat(client: httpx.Client, agent_id: str, text: str) -> dict[str, Any]:
    conversation = _json(
        client.post("/api/v1/conversations", json={"agentId": agent_id, "modelAlias": ALIAS})
    )
    posted = _json(
        client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"text": text},
        )
    )
    run = posted.get("run")
    if not isinstance(run, dict):
        raise SystemExit("message did not start a run")
    result = _wait(client, str(run["id"]))
    result["conversationId"] = conversation["id"]
    return result


def _note(name: str, body: object) -> None:
    print(f"step {name}", flush=True)
    path = Path(os.environ.get("M30_EVIDENCE", "m30-evidence.json"))
    current: dict[str, object] = {}
    if path.exists() and path.stat().st_size:
        loaded = orjson.loads(path.read_bytes())
        if isinstance(loaded, dict):
            current = loaded
    current[name] = body
    text = _scrub(json.dumps(current, indent=2, default=str))
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
        raise SystemExit("evidence still contains the provider key")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    stamp = str(int(time.time()))
    client = _client()
    _setup_model(client)
    uploaded = _json(
        client.post(
            "/api/v1/library-documents",
            files={"upload": ("dock.md", DOCK.encode(), "text/markdown")},
        )
    )
    standard = _json(
        client.post(
            "/api/v1/library-documents",
            files={"upload": ("standard.md", STANDARD.encode(), "text/markdown")},
        )
    )
    checked = _json(
        client.post(
            f"/api/v1/library-documents/{uploaded['id']}:judge",
            json={
                "ruleSet": {
                    "id": "dock",
                    "version": "1",
                    "items": [],
                    "sourceFileId": standard["id"],
                },
                "statements": ["The document must state the warehouse code for the north dock."],
                "label": "Dock rule set",
                "modelAlias": ALIAS,
            },
        )
    )
    collection = _json(
        client.post(
            "/api/v1/knowledge/collections",
            json={"name": "M30 library", "slug": f"m30-library-{stamp}", "description": "M30"},
        )
    )
    member = _json(
        client.post(
            f"/api/v1/knowledge/collections/{collection['id']}/members",
            json={"kind": "library", "libraryDocumentId": uploaded["id"]},
        )
    )
    _note(
        "documents",
        {
            "documentId": uploaded.get("id"),
            "checkSnippet": _scrub(json.dumps(checked))[:400],
            "chunks": member.get("chunks") or member.get("result"),
        },
    )
    clerk = _publish(
        client,
        f"m30-clerk-{stamp}",
        "M30 clerk",
        {
            "instructions": (
                "Answer from the knowledge passages. Cite the anchor. "
                "If no passage is attached, say the document is missing."
            ),
            "model": {"alias": ALIAS},
            "knowledge": {"collections": [collection.get("slug") or f"m30-library-{stamp}"]},
            "tools": [{"server": "documents", "version": "*", "include": ["read", "judge"]}],
            "budget": _budget(),
        },
    )
    cited = _chat(client, clerk, "What is the warehouse code for the north dock? Cite the passage.")
    _note("cited", cited)
    coder = _publish(
        client,
        f"m30-coder-{stamp}",
        "M30 coder",
        {
            "instructions": "Use general.code. Return only the number the script prints.",
            "model": {"alias": ALIAS},
            "tools": [{"server": "general", "version": "*", "include": ["code"]}],
            "budget": _budget(),
        },
    )
    coded = _chat(client, coder, "Use code to print 17 * 19. Reply with only that number.")
    _note("tool", coded)
    installed = client.post(
        "/api/v1/connectors/github:install",
        json={"connectionName": "github-public"},
    )
    if installed.status_code not in {200, 201, 409}:
        _json(installed)
    reader = _publish(
        client,
        f"m30-github-{stamp}",
        "GitHub reader",
        {
            "instructions": (
                "When asked to read a GitHub file, call github_read_file and quote the file text."
            ),
            "model": {"alias": ALIAS},
            "tools": [
                {
                    "server": "connectors",
                    "version": "*",
                    "include": ["github_read_file"],
                }
            ],
            "budget": _budget(),
        },
    )
    github = _chat(
        client,
        reader,
        "Use github_read_file with owner octocat, repo Hello-World and path README. "
        "Quote the first line.",
    )
    _note("github", github)
    red = f"m30-red-{stamp}"
    blue = f"m30-blue-{stamp}"
    child_def = {
        "instructions": "Reply with exactly the one word in the task. No other words.",
        "model": {"alias": ALIAS},
        "budget": _budget(),
    }
    _publish(client, red, "Red", child_def)
    _publish(client, blue, "Blue", child_def)
    lead = _publish(
        client,
        f"m30-lead-{stamp}",
        "Lead",
        {
            "instructions": (
                "Call agents_parallel once. Ask red to reply RED and blue to reply BLUE. "
                "Then answer exactly: RED and BLUE."
            ),
            "model": {"alias": ALIAS},
            "subagents": {
                "allowed": [red, blue],
                "maxDepth": 2,
                "maxParallel": 2,
                "childTimeoutS": 90,
            },
            "budget": _budget(),
        },
    )
    parallel = _chat(client, lead, "Use agents_parallel for red and blue, then combine the words.")
    kids = _items(client, f"/api/v1/runs/{parallel['runId']}/children")
    _note("children", {"count": len(kids), "parallel": parallel})
    exposed = _publish(
        client,
        f"m30-exposed-{stamp}",
        "Exposed",
        {
            "instructions": (
                "Answer in one short sentence. If asked for a number, give only the number."
            ),
            "model": {"alias": ALIAS},
            "budget": _budget(),
        },
    )
    created = _json(
        client.post(
            f"/api/v1/agents/{exposed}/api-keys",
            json={"label": "M30", "rateLimitRpm": 30, "monthlyQuota": 100},
        )
    )
    secret = str(created["key"])
    slug = f"m30-exposed-{stamp}"
    external = httpx.Client(base_url=BASE, timeout=180.0)
    external.headers["Authorization"] = f"Bearer {secret}"
    conversation = _json(external.post(f"/v1/agents/{slug}/conversations"))
    answer = _json(
        external.post(
            f"/v1/agents/{slug}/conversations/{conversation['id']}/messages",
            json={"text": "What is 2 + 2? Reply with only the number."},
        )
    )
    mcp = external.post(
        f"/v1/agents/{slug}/mcp",
        json={"jsonrpc": "2.0", "id": "1", "method": "tools/list"},
    )
    evidence = {
        "documentId": uploaded.get("id"),
        "standardId": standard.get("id"),
        "checkKeys": sorted(checked.keys()),
        "checkSnippet": _scrub(json.dumps(checked))[:400],
        "collection": collection.get("slug"),
        "memberChunks": member.get("chunks") or member.get("result"),
        "cited": cited,
        "tool": coded,
        "github": github,
        "children": len(kids),
        "parallel": parallel,
        "restSnippet": _scrub(json.dumps(answer))[:300],
        "mcpStatus": mcp.status_code,
    }
    text = _scrub(json.dumps(evidence, indent=2, default=str))
    secret_value = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret_value and secret_value in text:
        raise SystemExit("evidence still contains the provider key")
    if secret and secret in text:
        text = text.replace(secret, "[redacted-agent-key]")
    print(text)


if __name__ == "__main__":
    main()
