"""Live proof for orchestration.

The model key is read from AR_CERT_LLM_API_KEY and is never printed.
"""

from __future__ import annotations

import os
import time
from typing import Any  # noqa: TC003

import httpx

from ar_common.time import utcnow
from ar_domain.routines.signature import header_for

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18128")
ALIAS = "qwenm28"


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
    rows = _json(client.get(path)).get("items")
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
                "name": "DeepInfra M28",
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


def _budget(tool_calls: int, cost: int, wall: int = 180) -> dict[str, int]:
    return {
        "maxSteps": 8,
        "maxToolCalls": tool_calls,
        "maxWallClockS": wall,
        "maxCostMicros": cost,
        "maxTokens": 8000,
    }


def _publish(client: httpx.Client, slug: str, name: str, definition: dict[str, Any]) -> str:
    agent = _json(
        client.post(
            "/api/v1/agents",
            json={"slug": slug, "name": name, "visibility": "private", "definition": definition},
        )
    )
    _json(client.post(f"/api/v1/agents/{agent['id']}:publish", json={"changeNote": "proof"}))
    return str(agent["id"])


def _wait(client: httpx.Client, run_id: str, seconds: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    current: dict[str, Any] = {}
    while time.monotonic() < deadline:
        current = _json(client.get(f"/api/v1/runs/{run_id}"))
        status = str(current.get("status") or "")
        if status not in {"queued", "running"}:
            return current
        time.sleep(2)
    return current


def _chat(client: httpx.Client, agent_id: str, text: str) -> str:
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
    return str(run["id"])


def _children(client: httpx.Client, run_id: str) -> list[dict[str, Any]]:
    return _items(client, f"/api/v1/runs/{run_id}/children")


def main() -> None:
    stamp = str(int(time.time()))
    client = _client()
    _setup_model(client)
    child = {
        "instructions": "Reply with exactly the one word in the task. No other words.",
        "model": {"alias": ALIAS},
        "budget": _budget(2, 2_000_000),
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
            "budget": _budget(4, 5_000_000),
        },
    )
    parallel_id = _chat(
        client,
        parent,
        "Use agents_parallel for red and blue, then combine their one-word answers.",
    )
    parallel = _wait(client, parallel_id)
    kids = _children(client, parallel_id)

    slow = _publish(
        client,
        f"slow-{stamp}",
        "Slow",
        {
            "instructions": "Write a long essay. Do not stop early.",
            "model": {"alias": ALIAS},
            "budget": _budget(2, 2_000_000, 90),
        },
    )
    rescue = _publish(
        client,
        f"rescue-{stamp}",
        "Rescue",
        {
            "instructions": (
                "Call the slow agent. If it fails or times out, answer exactly: "
                "RECOVERED because the child failed."
            ),
            "model": {"alias": ALIAS},
            "subagents": {
                "allowed": [f"slow-{stamp}"],
                "maxDepth": 2,
                "maxParallel": 1,
                "childTimeoutS": 1,
            },
            "budget": _budget(4, 5_000_000),
        },
    )
    rescue_id = _chat(client, rescue, "Call the slow agent and recover if it fails.")
    rescued = _wait(client, rescue_id)
    rescue_kids = _children(client, rescue_id)

    loop = _publish(
        client,
        f"loop-{stamp}",
        "Loop",
        {
            "instructions": (
                "Call yourself with agents_call and the task again. Never answer in prose first."
            ),
            "model": {"alias": ALIAS},
            "subagents": {
                "allowed": [],
                "allowSelfClone": True,
                "maxDepth": 1,
                "maxParallel": 1,
                "childTimeoutS": 30,
            },
            "budget": _budget(2, 3, 60),
        },
    )
    loop_id = _chat(client, loop, "Keep calling yourself.")
    limited = _wait(client, loop_id)

    asker = _publish(
        client,
        f"ask-{stamp}",
        "Asker",
        {
            "instructions": (
                "Call agents_ask with question 'Which colour?' and options blue and red. "
                "When the person answers, reply with that word and nothing else."
            ),
            "model": {"alias": ALIAS},
            "human": {"enabled": True},
            "budget": _budget(4, 5_000_000),
        },
    )
    ask_id = _chat(client, asker, "Ask me which colour, then use my answer.")
    paused = _wait(client, ask_id)
    inbox = _items(client, "/api/v1/inbox")
    question = next((row for row in inbox if row.get("runId") == ask_id), None)
    answered: dict[str, Any] = {}
    if question is not None:
        _json(
            client.post(
                f"/api/v1/inbox/{question['id']}:answer",
                json={"text": "blue"},
            )
        )
        answered = _wait(client, ask_id)

    clerk = _publish(
        client,
        f"clerk-{stamp}",
        "Clerk",
        {
            "instructions": "Reply with the single word PING.",
            "model": {"alias": ALIAS},
            "budget": _budget(2, 2_000_000),
        },
    )
    routine = _json(
        client.post(
            "/api/v1/routines",
            json={
                "name": f"m28-{stamp}",
                "agentId": clerk,
                "instructions": "Reply with the single word PING.",
                "concurrencyPolicy": "skip",
                "trigger": {
                    "type": "schedule",
                    "cron": "0 9 * * 1",
                    "timezone": "UTC",
                    "executeModel": True,
                },
                "delivery": [{"type": "conversation"}],
            },
        )
    )
    fired = _json(client.post(f"/api/v1/routines/{routine['id']}:tick", json={"force": True}))
    schedule_run = (
        _wait(client, str(fired.get("runId") or fired.get("run_id") or ""))
        if fired.get("runId") or fired.get("run_id")
        else fired
    )

    hook = _json(
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
    secret = str((hook.get("webhook") or {}).get("webhookSecret") or "")
    url = str((hook.get("webhook") or {}).get("webhookUrl") or "")
    body = b'{"hello":"m28"}'
    header = header_for(secret, body, int(utcnow().timestamp()))
    first = client.post(url, content=body, headers={"x-ar-signature": header})
    second = client.post(url, content=body, headers={"x-ar-signature": header})
    hook_run = {}
    if first.status_code < 300:
        event_id = first.json().get("eventId") or first.json().get("event_id")
        events = _items(client, f"/api/v1/routines/{hook['id']}/events")
        match = next((row for row in events if str(row.get("id")) == str(event_id)), None)
        if match and match.get("runId"):
            hook_run = _wait(client, str(match["runId"]))

    evidence = {
        "parallel": {
            "status": parallel.get("status"),
            "summary": _scrub(str(parallel.get("resultSummary") or ""))[:500],
            "children": [
                {"slug": row.get("agentSlug"), "status": row.get("status")} for row in kids
            ],
        },
        "recover": {
            "status": rescued.get("status"),
            "summary": _scrub(str(rescued.get("resultSummary") or ""))[:500],
            "children": [
                {
                    "status": row.get("status"),
                    "error": (row.get("error") or {}).get("code")
                    if isinstance(row.get("error"), dict)
                    else None,
                }
                for row in rescue_kids
            ],
        },
        "budget": {
            "status": limited.get("status"),
            "summary": _scrub(str(limited.get("resultSummary") or ""))[:500],
            "error": limited.get("error"),
        },
        "schedule": {
            "tick": {k: fired.get(k) for k in ("status", "runId", "message")},
            "run": {
                "status": schedule_run.get("status") if isinstance(schedule_run, dict) else None,
                "summary": _scrub(str(schedule_run.get("resultSummary") or ""))[:300]
                if isinstance(schedule_run, dict)
                else None,
            },
        },
        "webhook": {
            "first": first.status_code,
            "second": second.status_code,
            "run": {
                "status": hook_run.get("status"),
                "summary": _scrub(str(hook_run.get("resultSummary") or ""))[:300],
            },
        },
        "question": {
            "paused": paused.get("status"),
            "answered": answered.get("status"),
            "summary": _scrub(str(answered.get("resultSummary") or ""))[:300],
        },
        "slowAgent": slow,
    }
    print(__import__("json").dumps(evidence, default=str, indent=2))


if __name__ == "__main__":
    main()
