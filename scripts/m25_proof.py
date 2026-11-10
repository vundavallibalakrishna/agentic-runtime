"""Live M25 proof. The provider key is read from the environment and never stored."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import httpx
import orjson
from sign_in import sign_in

BASE = os.environ.get("M25_API", "http://127.0.0.1:18125")
ROOT = Path(os.environ.get("M25_ROOT", str(Path(tempfile.gettempdir()) / "m25-proof")))
PHASE = os.environ.get("M25_PHASE", "all")
DOWNLOADS = {
    "gpl-3.0.txt": "https://www.gnu.org/licenses/gpl-3.0.txt",
    "rfc9110.txt": "https://www.rfc-editor.org/rfc/rfc9110.txt",
}
DOCK = (
    "# North dock\n\nThe warehouse code for the north dock is ND-1844-QUILL. "
    "It is not written in any public standard.\n"
)
SKILL = """---
name: Weekly status
slug: weekly-status
description: Use when the user asks for a weekly status note in the house style.
examples: Draft the weekly status
---

Begin the answer with the exact token STATUS-OK and then write exactly three short sentences.
"""


def _scrub(text: str) -> str:
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
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


def _json(response: httpx.Response) -> dict[str, object]:
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


def _items(client: httpx.Client, path: str) -> list[dict[str, object]]:
    body = _json(client.get(path))
    rows = body.get("items")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _record(name: str, body: object) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / "evidence.json"
    current: dict[str, object] = {}
    if path.exists():
        loaded = orjson.loads(path.read_bytes())
        if isinstance(loaded, dict):
            current = loaded
    current[name] = body
    text = _scrub(json.dumps(current, indent=2, default=str))
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
        raise SystemExit("evidence still contains the provider key")
    path.write_text(text)


def _state() -> dict[str, object]:
    loaded = orjson.loads((ROOT / "state.json").read_bytes())
    if not isinstance(loaded, dict):
        raise SystemExit("state was not an object")
    return loaded


def _save_state(body: dict[str, object]) -> None:
    (ROOT / "state.json").write_text(json.dumps(body, indent=2))


def _download(name: str, url: str) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / name
    cached = Path(tempfile.gettempdir()) / "m24-proof" / name
    if path.exists() and path.stat().st_size > 1000:
        return path
    if cached.exists() and cached.stat().st_size > 1000:
        path.write_bytes(cached.read_bytes())
        return path
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(url, headers={"User-Agent": "agentic-runtime-m25"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        path.write_bytes(response.read())
    return path


def _setup(client: httpx.Client) -> None:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("AR_CERT_LLM_API_KEY is missing")
    aliases = _items(client, "/api/v1/model-aliases")
    if not any(row.get("alias") == "qwenm25" for row in aliases):
        provider = _json(
            client.post(
                "/api/v1/model-providers",
                json={
                    "name": "DeepInfra M25",
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
                json={"alias": "qwenm25", "kind": "chat", "primaryModelId": chat["id"]},
            )
        )
        _json(
            client.post(
                "/api/v1/model-aliases",
                json={"alias": "bge-m3", "kind": "embedding", "primaryModelId": embed["id"]},
            )
        )
        tested = _json(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
    else:
        tested = {"ok": True, "reused": True}
    _record("provider", {"ok": tested.get("ok"), "embeddingModel": "BAAI/bge-m3"})


def _upload_library(client: httpx.Client, name: str, data: bytes, mime: str) -> dict[str, object]:
    return _json(client.post("/api/v1/library-documents", files={"upload": (name, data, mime)}))


def _wait_run(client: httpx.Client, run_id: str, conversation_id: str = "") -> dict[str, object]:
    deadline = time.monotonic() + 240
    status = ""
    summary = ""
    while time.monotonic() < deadline:
        current = _json(client.get(f"/api/v1/runs/{run_id}"))
        status = str(current.get("status") or "")
        summary = _scrub(str(current.get("resultSummary") or ""))
        if status in {"completed", "failed", "waiting_approval", "budget_exceeded", "cancelled"}:
            break
        time.sleep(2)
    if not conversation_id:
        run = _json(client.get(f"/api/v1/runs/{run_id}"))
        conversation_id = str(run.get("conversationId") or "")
    message = {}
    if conversation_id:
        conversation = _json(client.get(f"/api/v1/conversations/{conversation_id}"))
        messages = conversation.get("messages")
        if isinstance(messages, list):
            for row in messages:
                if isinstance(row, dict) and row.get("role") == "assistant":
                    message = row
    return {
        "status": status,
        "summary": summary[:2000],
        "text": _scrub(str(message.get("text") or ""))[:2000],
        "loadedSkill": message.get("loadedSkill"),
        "retrieval": message.get("retrieval"),
        "content": message.get("content"),
    }


def _ask(client: httpx.Client, agent_id: str, text: str) -> dict[str, object]:
    conversation = _json(
        client.post(
            "/api/v1/conversations",
            json={"agentId": agent_id, "modelAlias": "qwenm25"},
        )
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
    result = _wait_run(client, str(run["id"]), str(conversation["id"]))
    result["conversationId"] = conversation["id"]
    return result


def _build(client: httpx.Client) -> dict[str, object]:
    rows = _items(client, "/api/v1/knowledge/collections")
    existing = next((row for row in rows if row.get("slug") == "proof-library"), None)
    if existing is not None:
        return _finish_existing(client, existing)
    files = {name: _download(name, url) for name, url in DOWNLOADS.items()}
    dock = _upload_library(client, "dock.md", DOCK.encode(), "text/markdown")
    uploaded = {"dock.md": dock}
    for name, path in files.items():
        mime = "application/pdf" if path.suffix == ".pdf" else "text/plain"
        uploaded[name] = _upload_library(client, name, path.read_bytes(), mime)
    collection = _json(
        client.post(
            "/api/v1/knowledge/collections",
            json={"name": "Proof library", "slug": "proof-library", "description": "M25 proof"},
        )
    )
    if collection.get("embeddingModel") in {None, "", "fake-embed", "embed"}:
        raise SystemExit(
            f"collection stayed on a fake embedding: {collection.get('embeddingModel')}"
        )
    members = {}
    for name, row in uploaded.items():
        timeout = 900.0 if name.endswith(".pdf") else 180.0
        added = _json(
            client.post(
                f"/api/v1/knowledge/collections/{collection['id']}/members",
                json={"kind": "library", "libraryDocumentId": row["id"]},
                timeout=timeout,
            )
        )
        members[name] = {"result": added.get("result"), "chunks": added.get("chunks")}
    skill = _json(client.post("/api/v1/skills:import", json={"markdown": SKILL}))
    memory = _json(
        client.post(
            "/api/v1/memory",
            json={
                "content": "Call the user Captain Bala",
                "scope": "user",
                "category": "preference",
            },
        )
    )
    agent = _json(
        client.post(
            "/api/v1/agents",
            json={
                "slug": "proof-clerk",
                "name": "Proof clerk",
                "description": "M25 proof",
                "definition": _definition(with_knowledge=True),
            },
        )
    )
    _json(
        client.put(
            f"/api/v1/agents/{agent['id']}/versions/draft",
            json={"definition": _definition(with_knowledge=True), "changeNote": "m25"},
        )
    )
    _json(
        client.post(
            f"/api/v1/agents/{agent['id']}:publish",
            json={"changeNote": "m25", "skipEvalGate": True},
        )
    )
    bare = _json(
        client.post(
            "/api/v1/agents",
            json={
                "slug": "proof-bare",
                "name": "Proof bare",
                "description": "No knowledge base",
                "definition": _definition(with_knowledge=False),
            },
        )
    )
    _json(
        client.put(
            f"/api/v1/agents/{bare['id']}/versions/draft",
            json={"definition": _definition(with_knowledge=False), "changeNote": "m25 bare"},
        )
    )
    _json(
        client.post(
            f"/api/v1/agents/{bare['id']}:publish",
            json={"changeNote": "m25 bare", "skipEvalGate": True},
        )
    )
    state = {
        "collectionId": collection["id"],
        "embeddingModel": collection.get("embeddingModel"),
        "documents": {name: row.get("id") for name, row in uploaded.items()},
        "pages": {name: row.get("pageCount") for name, row in uploaded.items()},
        "members": members,
        "skillId": skill.get("id"),
        "memoryId": memory.get("id"),
        "agentId": agent["id"],
        "bareAgentId": bare["id"],
    }
    _save_state(state)
    _record("indexed", state)
    return state


def _finish_existing(client: httpx.Client, collection: dict[str, object]) -> dict[str, object]:
    library = {str(row.get("filename")): row for row in _items(client, "/api/v1/library-documents")}
    skills = _items(client, "/api/v1/skills")
    skill = next((row for row in skills if row.get("slug") == "weekly-status"), None)
    if skill is None:
        skill = _json(client.post("/api/v1/skills:import", json={"markdown": SKILL}))
    memory = _json(
        client.post(
            "/api/v1/memory",
            json={
                "content": "Call the user Captain Bala",
                "scope": "user",
                "category": "preference",
            },
        )
    )
    agent = _agent(client, "proof-clerk", "Proof clerk", with_knowledge=True)
    bare = _agent(client, "proof-bare", "Proof bare", with_knowledge=False)
    state = {
        "collectionId": collection["id"],
        "embeddingModel": collection.get("embeddingModel"),
        "documents": {name: row.get("id") for name, row in library.items()},
        "pages": {name: row.get("pageCount") for name, row in library.items()},
        "skillId": skill.get("id"),
        "memoryId": memory.get("id"),
        "agentId": agent["id"],
        "bareAgentId": bare["id"],
    }
    _save_state(state)
    _record("indexed", state)
    return state


def _agent(
    client: httpx.Client, slug: str, name: str, *, with_knowledge: bool
) -> dict[str, object]:
    agents = _items(client, "/api/v1/agents")
    found = next((row for row in agents if row.get("slug") == slug), None)
    if found is None:
        found = _json(
            client.post(
                "/api/v1/agents",
                json={
                    "slug": slug,
                    "name": name,
                    "description": "M25 proof",
                    "definition": _definition(with_knowledge=with_knowledge),
                },
            )
        )
    _json(
        client.put(
            f"/api/v1/agents/{found['id']}/versions/draft",
            json={"definition": _definition(with_knowledge=with_knowledge), "changeNote": "m25"},
        )
    )
    _json(
        client.post(
            f"/api/v1/agents/{found['id']}:publish",
            json={"changeNote": "m25", "skipEvalGate": True},
        )
    )
    return found


def _definition(*, with_knowledge: bool) -> dict[str, object]:
    knowledge: dict[str, object] = {"collections": ["proof-library"] if with_knowledge else []}
    return {
        "instructions": (
            "Answer from the knowledge passages when they are attached. "
            "Cite the anchor. If a skill was loaded, follow it. "
            "Use a remembered preference when one is in the prompt. "
            "If no passages are attached, say you do not have the document and do not guess a code."
        ),
        "model": {"alias": "qwenm25"},
        "skills": ["weekly-status"],
        "knowledge": knowledge,
        "budget": {"max_steps": 4, "max_tool_calls": 2, "max_wall_clock_s": 180},
    }


def _prove(client: httpx.Client, state: dict[str, object]) -> None:
    agent_id = str(state["agentId"])
    cited = _ask(client, agent_id, "What is the warehouse code for the north dock?")
    _record("cited", cited)
    text = str(cited.get("text") or "")
    if "ND-1844-QUILL" not in text and "ND-1844-QUILL" not in str(cited.get("summary")):
        raise SystemExit("the cited answer missed the dock code")
    retrieval = cited.get("retrieval")
    if not isinstance(retrieval, dict) or not retrieval.get("hits"):
        raise SystemExit("the answer had no retrieval trace")
    used = int(retrieval.get("usedChars") or retrieval.get("used_chars") or 0)
    if used > 12_000:
        raise SystemExit(f"retrieval used {used} characters")
    bare = _ask(
        client,
        str(state["bareAgentId"]),
        "What is the warehouse code for the north dock?",
    )
    _record("detached", bare)
    bare_text = str(bare.get("text") or "") + str(bare.get("summary") or "")
    if "ND-1844-QUILL" in bare_text:
        raise SystemExit("the detached agent invented the dock code")
    skilled = _ask(client, agent_id, "Write the weekly status note for the docks.")
    _record("skill", skilled)
    loaded = skilled.get("loadedSkill")
    if not isinstance(loaded, dict) or loaded.get("slug") != "weekly-status":
        raise SystemExit(f"skill was not loaded: {loaded}")
    if "STATUS-OK" not in str(skilled.get("text") or "") and "STATUS-OK" not in str(
        skilled.get("summary") or ""
    ):
        raise SystemExit("the answer did not follow the skill")
    remembered = _ask(client, agent_id, "What should you call me?")
    _record("memory", remembered)
    if "Captain Bala" not in str(remembered.get("text") or "") + str(remembered.get("summary")):
        raise SystemExit("memory did not carry the preference")
    _json(
        client.patch(
            f"/api/v1/memory/{state['memoryId']}",
            json={"content": "Call the user Captain Rivera"},
        )
    )
    corrected = _ask(client, str(state["bareAgentId"]), "What should you call me?")
    _record("memory-edited", corrected)
    if "Captain Rivera" not in str(corrected.get("text") or "") + str(corrected.get("summary")):
        raise SystemExit("the edited memory was not used")
    long = _ask(
        client,
        agent_id,
        "Which passage discusses account management control AC-2? Cite the page.",
    )
    _record("long-document", long)
    long_retrieval = long.get("retrieval")
    if not isinstance(long_retrieval, dict):
        raise SystemExit("the long document had no retrieval trace")
    long_used = int(long_retrieval.get("usedChars") or long_retrieval.get("used_chars") or 0)
    if long_used <= 0 or long_used > 12_000:
        raise SystemExit(f"long retrieval budget was {long_used}")
    hits = long_retrieval.get("hits")
    blob = json.dumps(hits)
    if "AC-2" not in blob and "Account Management" not in blob and "account management" not in blob:
        raise SystemExit("the long retrieval did not surface account management")


def _restart_check(client: httpx.Client) -> None:
    state = _state()
    collections = _items(client, "/api/v1/knowledge/collections")
    if not any(row.get("id") == state["collectionId"] for row in collections):
        raise SystemExit("the knowledge base did not survive restart")
    found = _json(
        client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "warehouse code for the north dock",
                "collectionIds": [state["collectionId"]],
            },
        )
    )
    blob = json.dumps(found)
    if "ND-1844-QUILL" not in blob:
        raise SystemExit("search after restart missed the dock code")
    skills = _items(client, "/api/v1/skills")
    if not any(row.get("id") == state["skillId"] for row in skills):
        raise SystemExit("the skill did not survive restart")
    memory = _items(client, "/api/v1/memory")
    if not any("Captain Rivera" in str(row.get("content")) for row in memory):
        raise SystemExit("the edited memory did not survive restart")
    _record("restart", {"ok": True, "hits": len(found.get("hits") or [])})


def main() -> None:
    client = _client()
    if PHASE in {"all", "build"}:
        _setup(client)
        state = _build(client)
        if PHASE == "all":
            _prove(client, state)
    elif PHASE == "prove":
        _prove(client, _state())
    elif PHASE == "restart":
        _restart_check(client)
    else:
        raise SystemExit(f"unknown phase {PHASE}")


if __name__ == "__main__":
    main()
