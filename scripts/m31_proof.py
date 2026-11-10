# ruff: noqa: E501, S108, S310, TC003, TID251, PLC0415
"""Live M31 certification. The provider key is read from the environment and never stored.

Evidence is written under /tmp/m31-proof. Secrets are stripped before anything is written.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import httpx
import psycopg
from sign_in import sign_in

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18131")
ROOT = Path(os.environ.get("M31_ROOT", "/tmp/m31-proof"))
DSN = os.environ.get("M31_DSN", "postgresql://ar_owner:ar_owner@127.0.0.1:5432/m31_fresh")
ALIAS = "qwenm31"
PDF = Path("/workspace/docs/architecture/agentic-runtime-architecture.pdf")
PHASE = os.environ.get("M31_PHASE", "all")


def _secrets() -> list[str]:
    values = [os.environ.get("AR_CERT_LLM_API_KEY", ""), _gh_token()]
    return [item for item in values if item]


def _gh_token() -> str:
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        )
    except OSError, subprocess.CalledProcessError:
        return ""
    return completed.stdout.strip()


def _scrub(text: str) -> str:
    for secret in _secrets():
        if secret in text:
            text = text.replace(secret, "[redacted]")
    return text


def _client() -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=180.0, follow_redirects=False)
    client.cookies.update(sign_in(BASE, "admin@dev.local"))
    token = client.cookies.get("ar_csrf")
    if not token:
        raise SystemExit("dev login did not set a CSRF cookie")
    client.headers["x-csrf-token"] = token
    return client


def _body(response: httpx.Response) -> dict[str, Any]:
    text = _scrub(response.text)
    if response.status_code >= 300:
        raise SystemExit(f"{response.request.method} {response.status_code} {text[:900]}")
    parsed = response.json()
    if not isinstance(parsed, dict):
        raise SystemExit("response was not an object")
    dumped = json.dumps(parsed)
    for secret in _secrets():
        if secret and secret in dumped:
            raise SystemExit("a response contained a secret")
    return parsed


def _items(client: httpx.Client, path: str) -> list[dict[str, Any]]:
    payload = _body(client.get(path))
    rows = payload.get("items")
    if rows is None:
        rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _record(name: str, body: object) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / "evidence.json"
    current: dict[str, object] = {}
    if path.exists() and path.stat().st_size:
        loaded = json.loads(path.read_text())
        if isinstance(loaded, dict):
            current = loaded
    current[name] = json.loads(_scrub(json.dumps(body, default=str)))
    text = json.dumps(current, indent=2)
    for secret in _secrets():
        if secret and secret in text:
            raise SystemExit(f"evidence {name} still contains a secret")
    path.write_text(text + "\n")
    print(f"recorded {name}", flush=True)


def _budget(
    steps: int = 8, calls: int = 6, wall: int = 180, cost: int = 5_000_000
) -> dict[str, int]:
    return {
        "maxSteps": steps,
        "maxToolCalls": calls,
        "maxWallClockS": wall,
        "maxCostMicros": cost,
        "maxTokens": 4000,
    }


def _setup_model(client: httpx.Client) -> dict[str, Any]:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("AR_CERT_LLM_API_KEY is missing")
    if any(row.get("alias") == ALIAS for row in _items(client, "/api/v1/model-aliases")):
        provider = next(
            row
            for row in _items(client, "/api/v1/model-providers")
            if row.get("name") == "DeepInfra M31"
        )
        tested = _body(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
        return {
            "reused": True,
            "providerTestOk": tested.get("ok"),
            "providerReply": _scrub(str(tested.get("output") or ""))[:240],
            "latencyMs": tested.get("latencyMs"),
            "hasApiKey": provider.get("hasApiKey"),
            "apiKeyField": "apiKey" in provider,
            "sealed": _sealed(key),
            "provider": _public_provider(provider),
        }
    provider = _body(
        client.post(
            "/api/v1/model-providers",
            json={
                "name": "DeepInfra M31",
                "kind": "openai_compatible",
                "baseUrl": "https://api.deepinfra.com/v1/openai",
                "apiKey": key,
            },
        )
    )
    dumped = json.dumps(provider)
    if key in dumped or "apiKey" in provider:
        raise SystemExit("provider response exposed the API key")
    chat = _body(
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
    embed = _body(
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
    _body(
        client.post(
            "/api/v1/model-aliases",
            json={"alias": ALIAS, "kind": "chat", "primaryModelId": chat["id"]},
        )
    )
    _body(
        client.post(
            "/api/v1/model-aliases",
            json={"alias": "bge-m3", "kind": "embedding", "primaryModelId": embed["id"]},
        )
    )
    tested = _body(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
    listed = next(
        row for row in _items(client, "/api/v1/model-providers") if row.get("id") == provider["id"]
    )
    sealed = _sealed(key)
    return {
        "providerTestOk": tested.get("ok"),
        "providerReply": _scrub(str(tested.get("output") or ""))[:240],
        "latencyMs": tested.get("latencyMs"),
        "hasApiKey": listed.get("hasApiKey"),
        "apiKeyField": "apiKey" in listed,
        "sealed": sealed,
        "provider": _public_provider(listed),
    }


def _public_provider(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "kind": row.get("kind"),
        "baseUrl": row.get("baseUrl"),
        "hasApiKey": row.get("hasApiKey"),
    }


def _sealed(key: str) -> dict[str, Any]:
    raw = key.encode()
    with psycopg.connect(DSN) as conn:
        rows = conn.execute("SELECT ciphertext FROM encrypted_secrets").fetchall()
    hits = 0
    for (blob,) in rows:
        data = bytes(blob) if blob is not None else b""
        if raw in data:
            hits += 1
    return {"secretRows": len(rows), "plaintextHits": hits}


def _publish(client: httpx.Client, slug: str, name: str, definition: dict[str, Any]) -> str:
    agent = _body(
        client.post(
            "/api/v1/agents",
            json={"slug": slug, "name": name, "visibility": "private", "definition": definition},
        )
    )
    _body(
        client.post(
            f"/api/v1/agents/{agent['id']}:publish",
            json={"changeNote": "m31", "skipEvalGate": True},
        )
    )
    return str(agent["id"])


def _wait(client: httpx.Client, run_id: str, seconds: int = 240) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    current: dict[str, Any] = {}
    while time.monotonic() < deadline:
        current = _body(client.get(f"/api/v1/runs/{run_id}"))
        if str(current.get("status") or "") not in {"queued", "running"}:
            break
        time.sleep(2)
    calls = client.get(f"/api/v1/runs/{run_id}/tool-calls")
    return {
        "status": current.get("status"),
        "summary": _scrub(str(current.get("resultSummary") or ""))[:800],
        "error": current.get("error"),
        "costMicros": current.get("costMicros") or current.get("cost_micros"),
        "durationMs": current.get("durationMs") or current.get("duration_ms"),
        "runId": run_id,
        "toolCalls": _scrub(calls.text)[:6000],
    }


def _chat(client: httpx.Client, agent_id: str, text: str, *, alias: str = ALIAS) -> dict[str, Any]:
    conversation = _body(
        client.post("/api/v1/conversations", json={"agentId": agent_id, "modelAlias": alias})
    )
    posted = _body(
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


def _tool_id(client: httpx.Client, qualified: str) -> str:
    for row in _items(client, "/api/v1/tools"):
        if row.get("qualifiedName") == qualified:
            return str(row.get("toolId") or row.get("id"))
    raise SystemExit(f"missing tool {qualified}")


def _call(client: httpx.Client, qualified: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _body(
        client.post(
            f"/api/v1/tools/{_tool_id(client, qualified)}:test",
            json={"arguments": arguments},
        )
    )
    return json.loads(_scrub(json.dumps(result, default=str)))


def _identity(client: httpx.Client) -> None:
    signup = client.post(
        "/api/v1/signup",
        json={"slug": "m31", "name": "M31", "email": "m31@example.com"},
    )
    conversations = _items(client, "/api/v1/conversations")
    agents = _items(client, "/api/v1/agents")
    openapi = client.get("/openapi.json")
    grc_paths = []
    if openapi.status_code < 300:
        document = openapi.json()
        paths = document.get("paths") if isinstance(document, dict) else {}
        if isinstance(paths, dict):
            grc_paths = [path for path in paths if "grc" in path.lower()]
    _record(
        "identity",
        {
            "signupStatus": signup.status_code,
            "signupBody": _scrub(signup.text)[:240],
            "conversationCount": len(conversations),
            "agents": [row.get("slug") for row in agents],
            "grcPaths": grc_paths,
        },
    )


def _tools(client: httpx.Client, stamp: str) -> None:
    _body(
        client.patch(
            "/api/v1/tenant",
            json={
                "settings": {
                    "egressAllowlist": [
                        "www.gnu.org",
                        "api.github.com",
                        "httpbin.org",
                    ]
                }
            },
        )
    )
    code_fail = _call(client, "general.code", {"source": "print(1/0)"})
    code_ok = _call(client, "general.code", {"source": "print(17 * 19)"})
    shell = _call(client, "general.shell", {"command": "printf 'm31-shell\\n'"})
    written = _call(
        client,
        "general.write_file",
        {"path": "/workspace/note.txt", "text": "m31 workspace note"},
    )
    listed = _call(client, "general.list_files", {"path": "/workspace"})
    read_back = _call(client, "general.read_file", {"path": "/workspace/note.txt"})
    fetched = _call(
        client,
        "general.fetch",
        {"url": "https://www.gnu.org/licenses/gpl-3.0.txt"},
    )
    http_get = _call(
        client,
        "general.http",
        {"method": "GET", "url": "https://api.github.com/zen"},
    )
    http_post = _call(
        client,
        "general.http",
        {"method": "POST", "url": "https://httpbin.org/post", "json": {"ok": True}},
    )
    _record(
        "tools",
        {
            "codeFail": _brief(code_fail),
            "codeOk": _brief(code_ok),
            "shell": _brief(shell),
            "write": _brief(written),
            "list": _brief(listed),
            "read": _brief(read_back),
            "fetch": _brief(fetched),
            "httpGet": _brief(http_get),
            "httpPost": {
                "status": http_post.get("status"),
                "approvalId": http_post.get("approvalId"),
                "text": _scrub(str(http_post.get("text") or http_post.get("resultPreview") or ""))[
                    :300
                ],
            },
        },
    )
    agent = _publish(
        client,
        f"m31-repair-{stamp}",
        "Repair",
        {
            "instructions": (
                "Use general.code. First run print(1/0). When that fails with ZeroDivisionError, "
                "run print(17*19) and reply with only that number. Do not skip the failing call."
            ),
            "model": {"alias": ALIAS},
            "tools": [{"server": "general", "version": "*", "include": ["code"]}],
            "budget": _budget(8, 4),
        },
    )
    repaired = _chat(
        client,
        agent,
        "Plan the two Python calls, run the failing one, recover, and finish with the number only.",
    )
    _record("repair", repaired)


def _brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": row.get("status"),
        "isError": row.get("isError"),
        "text": _scrub(str(row.get("text") or row.get("resultPreview") or ""))[:400],
        "error": row.get("error"),
    }


def _documents(client: httpx.Client) -> None:
    uploaded = _body(
        client.post(
            "/api/v1/library-documents",
            files={"upload": (PDF.name, PDF.read_bytes(), "application/pdf")},
        )
    )
    document_id = str(uploaded["id"])
    outline = _body(client.get(f"/api/v1/library-documents/{document_id}/outline"))
    summary = _body(
        client.post(
            f"/api/v1/library-documents/{document_id}:summarise",
            json={"modelAlias": ALIAS},
        )
    )
    passages = _body(
        client.get(f"/api/v1/library-documents/{document_id}/passages?pageFrom=1&pageTo=2")
    )
    rows = passages.get("passages")
    anchor = ""
    quote = ""
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        anchor = str(rows[0].get("anchor") or "")
        quote = str(rows[0].get("text") or "")[:180]
    checked = _body(
        client.post(
            f"/api/v1/library-documents/{document_id}:judge",
            json={
                "statements": [
                    quote[:120] or "architecture",
                    "The organisation shall operate a colony on Mars",
                ],
                "label": "architecture and a missing requirement",
                "modelAlias": ALIAS,
            },
        )
    )
    gpl = _download("gpl-3.0.txt", "https://www.gnu.org/licenses/gpl-3.0.txt")
    gpl2 = _download("gpl-2.0.txt", "https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt")
    left = _body(
        client.post(
            "/api/v1/library-documents",
            files={"upload": ("gpl-3.0.txt", gpl.read_bytes(), "text/plain")},
        )
    )
    right = _body(
        client.post(
            "/api/v1/library-documents",
            files={"upload": ("gpl-2.0.txt", gpl2.read_bytes(), "text/plain")},
        )
    )
    compared = _body(
        client.post(
            f"/api/v1/library-documents/{left['id']}:compare",
            json={"otherDocumentId": right["id"], "modelAlias": ALIAS},
        )
    )
    gpl_passages = _body(
        client.get(f"/api/v1/library-documents/{left['id']}/passages?pageFrom=1&pageTo=1")
    )
    gpl_rows = gpl_passages.get("passages")
    gpl_anchor = ""
    if isinstance(gpl_rows, list) and gpl_rows and isinstance(gpl_rows[0], dict):
        gpl_anchor = str(gpl_rows[0].get("anchor") or "")
    rewrite = _body(
        client.post(
            f"/api/v1/library-documents/{left['id']}:rewrite",
            json={
                "anchor": gpl_anchor,
                "instruction": "Rephrase this passage in simpler words. Do not add facts.",
                "modelAlias": ALIAS,
            },
        )
    )
    before = _body(client.get(f"/api/v1/document-rewrites/{rewrite['id']}"))
    accepted = _body(
        client.post(
            f"/api/v1/document-rewrites/{rewrite['id']}:decide",
            json={"decision": "accept"},
        )
    )
    _record(
        "documents",
        {
            "pdf": {
                "id": document_id,
                "pages": uploaded.get("pageCount"),
                "name": uploaded.get("filename"),
            },
            "outline": _trim(outline),
            "summary": _trim(summary),
            "anchor": anchor,
            "check": _trim(checked),
            "compare": {
                "id": compared.get("id"),
                "status": compared.get("status"),
                "changes": compared.get("changes"),
            },
            "rewriteBefore": before.get("status"),
            "rewriteAfter": accepted.get("status"),
        },
    )


def _trim(value: object) -> object:
    text = _scrub(json.dumps(value, default=str))
    if len(text) <= 1800:
        return json.loads(text)
    return text[:1800]


def _download(name: str, url: str) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / name
    if path.exists() and path.stat().st_size > 1000:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "agentic-runtime-m31"})
    with urllib.request.urlopen(request, timeout=90) as response:
        path.write_bytes(response.read())
    return path


def _knowledge(client: httpx.Client, stamp: str) -> None:
    source = (
        "# North dock\n\nThe warehouse code for the north dock is ND-1844-QUILL. "
        "It is not written in any public standard.\n"
    )
    library = _body(
        client.post(
            "/api/v1/library-documents",
            files={"upload": ("north-dock.md", source.encode(), "text/markdown")},
        )
    )
    collection = _body(
        client.post(
            "/api/v1/knowledge/collections",
            json={
                "name": f"M31 library {stamp}",
                "slug": f"m31-library-{stamp}",
                "description": "Certification library",
                "embeddingAlias": "bge-m3",
            },
        )
    )
    added = _body(
        client.post(
            f"/api/v1/knowledge/collections/{collection['id']}/members",
            json={"kind": "library", "libraryDocumentId": library["id"]},
        )
    )
    skill = _body(
        client.post(
            "/api/v1/skills:import",
            json={
                "markdown": (
                    "---\n"
                    "name: Weekly status\n"
                    "slug: weekly-status\n"
                    "description: Use when the user asks for a weekly status note in the house style.\n"
                    "examples: Draft the weekly status\n"
                    "---\n\n"
                    "Begin the answer with the exact token STATUS-OK and then write exactly three short sentences.\n"
                )
            },
        )
    )
    memory = _body(
        client.post(
            "/api/v1/memory",
            json={
                "content": "Call the user Captain Bala",
                "scope": "user",
                "category": "preference",
            },
        )
    )
    definition = {
        "instructions": (
            "Answer from the knowledge passages when they are attached. Cite the anchor. "
            "If a skill was loaded, follow it. Use a remembered preference when one is in the prompt. "
            "If no passages are attached, say you do not have the document and do not guess a code."
        ),
        "model": {"alias": ALIAS},
        "skills": ["weekly-status"],
        "knowledge": {"collections": [f"m31-library-{stamp}"]},
        "budget": _budget(4, 2),
    }
    agent = _publish(client, f"m31-clerk-{stamp}", "Clerk", definition)
    bare = _publish(
        client,
        f"m31-bare-{stamp}",
        "Bare",
        {**definition, "knowledge": {"collections": []}, "skills": []},
    )
    cited = _chat(client, agent, "What is the warehouse code for the north dock?")
    detached = _chat(client, bare, "What is the warehouse code for the north dock?")
    skilled = _chat(client, agent, "Write the weekly status note for the docks.")
    remembered = _chat(client, agent, "What should you call me?")
    edited = _body(
        client.patch(
            f"/api/v1/memory/{memory['id']}",
            json={"content": "Call the user Captain Rivera"},
        )
    )
    corrected = _chat(client, bare, "What should you call me?")
    _record(
        "knowledge",
        {
            "embeddingModel": collection.get("embeddingModel"),
            "chunks": added.get("chunks") or added.get("result"),
            "cited": {"status": cited.get("status"), "summary": cited.get("summary")},
            "detached": {"status": detached.get("status"), "summary": detached.get("summary")},
            "skill": {
                "status": skilled.get("status"),
                "summary": skilled.get("summary"),
                "skillId": skill.get("id"),
            },
            "memoryBefore": remembered.get("summary"),
            "memoryEdited": edited.get("content") or edited.get("text"),
            "memoryAfter": corrected.get("summary"),
        },
    )


def _connectors(client: httpx.Client) -> None:
    catalog = _items(client, "/api/v1/connectors")
    labels = [{"slug": row.get("slug"), "verification": row.get("verification")} for row in catalog]
    _body(
        client.post("/api/v1/connectors/github:install", json={"connectionName": "github-public"})
    )
    read = _call(
        client,
        "connectors.github_read_file",
        {"owner": "octocat", "repo": "Hello-World", "path": "README"},
    )
    issue: dict[str, Any] = {"attempted": False}
    token = _gh_token()
    if token:
        _body(
            client.post(
                "/api/v1/service-connections",
                json={"name": "github-write", "kind": "bearer", "secret": token},
            )
        )
        installs = _items(client, "/api/v1/connectors")
        github = next(row for row in installs if row.get("slug") == "github")
        install_id = str(github.get("installId") or "")
        if install_id:
            _body(
                client.patch(
                    f"/api/v1/connector-installs/{install_id}",
                    json={"connectionName": "github-write"},
                )
            )
        created = _call(
            client,
            "connectors.github_create_issue",
            {
                "owner": "vundavallibalakrishna",
                "repo": "agentic-runtime",
                "title": "M31 certification probe",
                "body": "Created by the M31 certification. Safe to close.",
            },
        )
        issue = {"attempted": True, "result": _brief(created)}
    _record(
        "connectors",
        {
            "catalog": labels,
            "githubRead": _brief(read),
            "githubIssue": issue,
            "tokenPresent": bool(token),
        },
    )


def _orchestration(client: httpx.Client, stamp: str) -> None:
    child = {
        "instructions": "Reply with exactly the one word in the task. No other words.",
        "model": {"alias": ALIAS},
        "budget": _budget(2, 2, cost=2_000_000),
    }
    _publish(client, f"red-{stamp}", "Red", child)
    _publish(client, f"blue-{stamp}", "Blue", child)
    parent = _publish(
        client,
        f"lead-{stamp}",
        "Lead",
        {
            "instructions": (
                "Call agents_parallel once. Ask red to reply RED and blue to reply BLUE. "
                "Then answer exactly: RED and BLUE."
            ),
            "model": {"alias": ALIAS},
            "subagents": {
                "allowed": [f"red-{stamp}", f"blue-{stamp}"],
                "maxDepth": 2,
                "maxParallel": 2,
                "childTimeoutS": 60,
            },
            "budget": _budget(4, 4),
        },
    )
    parallel = _chat(
        client,
        parent,
        "Use agents_parallel for red and blue, then combine their one-word answers.",
    )
    children = _items(client, f"/api/v1/runs/{parallel['runId']}/children")
    asker = _publish(
        client,
        f"ask-{stamp}",
        "Asker",
        {
            "instructions": (
                "Call agents_ask with kind approval and the question 'Ship it?' and no other assignee. "
                "Quote the tool error. Then call agents_ask with kind question, question 'Which colour?', "
                "and options blue and red. When the person answers, reply with that word only."
            ),
            "model": {"alias": ALIAS},
            "human": {"enabled": True},
            "budget": _budget(6, 4),
        },
    )
    asked = _chat(client, asker, "Ask for approval of yourself, then ask me which colour.")
    inbox = _items(client, "/api/v1/inbox")
    question = next((row for row in inbox if row.get("runId") == asked["runId"]), None)
    answered: dict[str, Any] = {}
    self_denied: dict[str, Any] = {}
    if question is not None and question.get("kind") == "approval":
        denied = client.post(
            f"/api/v1/inbox/{question['id']}:answer",
            json={"text": "approve"},
        )
        self_denied = {"status": denied.status_code, "body": _scrub(denied.text)[:300]}
    elif question is not None:
        _body(client.post(f"/api/v1/inbox/{question['id']}:answer", json={"text": "blue"}))
        answered = _wait(client, str(asked["runId"]))
    clerk = _publish(
        client,
        f"clerk-{stamp}",
        "Clerk",
        {
            "instructions": "Reply with the single word PING.",
            "model": {"alias": ALIAS},
            "budget": _budget(2, 1, cost=2_000_000),
        },
    )
    routine = _body(
        client.post(
            "/api/v1/routines",
            json={
                "name": f"m31-{stamp}",
                "agentId": clerk,
                "instructions": "Reply with the single word PING.",
                "concurrencyPolicy": "skip",
                "trigger": {
                    "type": "schedule",
                    "cron": "*/5 * * * *",
                    "timezone": "UTC",
                    "executeModel": True,
                },
                "delivery": [{"type": "conversation"}],
            },
        )
    )
    fired = _body(client.post(f"/api/v1/routines/{routine['id']}:tick", json={"force": True}))
    run_id = str(fired.get("runId") or fired.get("run_id") or "")
    schedule_run = _wait(client, run_id) if run_id else fired
    hook = _body(
        client.post(
            "/api/v1/routines",
            json={
                "name": f"hook-{stamp}",
                "agentId": clerk,
                "instructions": "Reply with the single word HOOK.",
                "trigger": {"type": "webhook", "executeModel": True},
                "delivery": [{"type": "conversation"}],
            },
        )
    )
    secret = str(
        (hook.get("webhook") or {}).get("webhookSecret") or hook.get("webhookSecret") or ""
    )
    url = str((hook.get("webhook") or {}).get("webhookUrl") or "")
    from ar_common.time import utcnow
    from ar_domain.routines.signature import header_for

    payload = b'{"hello":"m31"}'
    header = header_for(secret, payload, int(utcnow().timestamp()))
    first = client.post(url, content=payload, headers={"x-ar-signature": header})
    second = client.post(url, content=payload, headers={"x-ar-signature": header})
    _record(
        "orchestration",
        {
            "limits": {
                "maxDepth": 2,
                "maxParallel": 2,
                "childTimeoutS": 60,
                "maxCostMicros": 5_000_000,
            },
            "parallel": {
                "status": parallel.get("status"),
                "summary": parallel.get("summary"),
                "costMicros": parallel.get("costMicros"),
                "durationMs": parallel.get("durationMs"),
                "children": [
                    {"slug": row.get("agentSlug"), "status": row.get("status")} for row in children
                ],
            },
            "ask": {
                "status": asked.get("status"),
                "summary": asked.get("summary"),
                "toolCalls": asked.get("toolCalls"),
                "selfDenied": self_denied,
                "answered": answered.get("summary"),
            },
            "schedule": {
                "cron": "*/5 * * * *",
                "tick": {key: fired.get(key) for key in ("status", "runId", "run_id", "message")},
                "run": {
                    "status": schedule_run.get("status")
                    if isinstance(schedule_run, dict)
                    else None,
                    "summary": schedule_run.get("summary")
                    if isinstance(schedule_run, dict)
                    else None,
                },
            },
            "webhook": {"first": first.status_code, "second": second.status_code},
        },
    )


def _external(client: httpx.Client, stamp: str) -> None:
    agent_id = _publish(
        client,
        f"m31-exposed-{stamp}",
        "Exposed",
        {
            "instructions": "Reply with only the number that answers the question.",
            "model": {"alias": ALIAS},
            "budget": _budget(3, 1, cost=2_000_000),
        },
    )
    slug = f"m31-exposed-{stamp}"
    created = _body(
        client.post(
            f"/api/v1/agents/{agent_id}/api-keys",
            json={"label": "Certification", "rateLimitRpm": 30, "monthlyQuota": 100},
        )
    )
    secret = str(created["key"])
    external = httpx.Client(
        base_url=BASE,
        timeout=180.0,
        headers={"Authorization": f"Bearer {secret}"},
    )
    missing = httpx.Client(base_url=BASE, timeout=30.0).post(f"/v1/agents/{slug}/conversations")
    conversation = _body(external.post(f"/v1/agents/{slug}/conversations"))
    idem = f"m31-{stamp}"
    body = {"text": "What is 2 + 2? Reply with only the number."}
    first = _body(
        external.post(
            f"/v1/agents/{slug}/conversations/{conversation['id']}/messages",
            headers={"Idempotency-Key": idem},
            json=body,
        )
    )
    second = external.post(
        f"/v1/agents/{slug}/conversations/{conversation['id']}/messages",
        headers={"Idempotency-Key": idem},
        json=body,
    )
    streamed = external.post(
        f"/v1/agents/{slug}/conversations/{conversation['id']}/messages",
        json={"text": "Name the integer that comes after 4. One word.", "stream": True},
    )
    task = _body(
        external.post(
            f"/v1/agents/{slug}/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "m31",
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
    listed = _body(
        external.post(
            "/v1/mcp",
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    )
    called = _body(
        external.post(
            "/v1/mcp",
            headers={"Accept": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": f"agent_{slug.replace('-', '_')}",
                    "arguments": {"message": "What is 5 + 5? Reply with only the number."},
                },
            },
        )
    )
    tight = _body(
        client.post(
            f"/api/v1/agents/{agent_id}/api-keys",
            json={"label": "Tight", "rateLimitRpm": 2, "monthlyQuota": 10},
        )
    )
    tight_client = httpx.Client(
        base_url=BASE,
        timeout=30.0,
        headers={"Authorization": f"Bearer {tight['key']}"},
    )
    statuses = [
        tight_client.get(f"/v1/agents/{slug}/.well-known/agent-card.json").status_code
        for _ in range(3)
    ]
    _body(client.delete(f"/api/v1/agents/{agent_id}/api-keys/{created['id']}"))
    revoked = external.post(f"/v1/agents/{slug}/conversations")
    artifact = ""
    result = task.get("result")
    if isinstance(result, dict):
        artifacts = result.get("artifacts")
        if isinstance(artifacts, list) and artifacts and isinstance(artifacts[0], dict):
            parts = artifacts[0].get("parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], dict):
                artifact = str(parts[0].get("text") or "")
    evidence = {
        "slug": slug,
        "sync": {
            "output": first.get("output"),
            "status": first.get("status"),
            "id": first.get("id"),
        },
        "replay": {
            "status": second.status_code,
            "same": second.json().get("id") == first.get("id")
            if second.status_code < 300
            else False,
            "header": second.headers.get("idempotent-replayed"),
        },
        "stream": {
            "status": streamed.status_code,
            "contentType": streamed.headers.get("content-type"),
            "hasData": "data:" in streamed.text,
            "sample": _scrub(streamed.text)[:300],
        },
        "missing": missing.status_code,
        "revoked": revoked.status_code,
        "rate": statuses,
        "mcpTools": [
            item.get("name")
            for item in ((listed.get("result") or {}).get("tools") or [])
            if isinstance(item, dict)
        ]
        if isinstance(listed.get("result"), dict)
        else [],
        "mcpCall": (called.get("result") or {}).get("content")
        if isinstance(called.get("result"), dict)
        else called,
        "a2a": artifact[:200],
    }
    text = json.dumps(evidence)
    if secret in text or str(tight.get("key") or "") in text:
        raise SystemExit("external evidence contains a key")
    _record("external", evidence)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time()))
    client = _client()
    sections = {
        "identity": lambda: _identity(client),
        "model": lambda: _record("model", _setup_model(client)),
        "tools": lambda: _tools(client, stamp),
        "documents": lambda: _documents(client),
        "knowledge": lambda: _knowledge(client, stamp),
        "connectors": lambda: _connectors(client),
        "orchestration": lambda: _orchestration(client, stamp),
        "external": lambda: _external(client, stamp),
    }
    selected = list(sections) if PHASE == "all" else [PHASE]
    failures: list[str] = []
    for name in selected:
        try:
            sections[name]()
        except SystemExit as exc:
            failures.append(f"{name}: {exc}")
            _record(f"{name}-error", {"error": str(exc)[:800]})
            print(f"FAILED {name}: {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001 — keep the rest of the certification running
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            _record(f"{name}-error", {"error": f"{type(exc).__name__}: {exc}"[:800]})
            print(f"FAILED {name}: {type(exc).__name__}: {exc}", flush=True)
    _record("failures", failures)
    if failures:
        raise SystemExit("sections failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
