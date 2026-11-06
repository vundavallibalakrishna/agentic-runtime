# ruff: noqa: S108, SIM115, PTH123, TC003
"""Follow-up live checks that the first pass left incomplete. No secrets are written."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from sign_in import sign_in

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18131")
ALIAS = "qwenm31"


def _scrub(text: str) -> str:
    secret = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _client(email: str = "admin@dev.local") -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=180.0, follow_redirects=False)
    client.cookies.update(sign_in(BASE, email))
    token = client.cookies.get("ar_csrf")
    if not token:
        raise SystemExit("missing csrf")
    client.headers["x-csrf-token"] = token
    return client


def _body(response: httpx.Response) -> dict[str, Any]:
    text = _scrub(response.text)
    if response.status_code >= 300:
        raise SystemExit(f"{response.request.method} {response.status_code} {text[:700]}")
    parsed = response.json()
    if not isinstance(parsed, dict):
        raise SystemExit("not an object")
    return parsed


def _items(client: httpx.Client, path: str) -> list[dict[str, Any]]:
    payload = _body(client.get(path))
    rows = payload.get("items")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


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
            json={"changeNote": "m31 follow-up", "skipEvalGate": True},
        )
    )
    return str(agent["id"])


def _wait(client: httpx.Client, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 240
    current: dict[str, Any] = {}
    while time.monotonic() < deadline:
        current = _body(client.get(f"/api/v1/runs/{run_id}"))
        if str(current.get("status") or "") not in {"queued", "running"}:
            break
        time.sleep(2)
    calls = _scrub(client.get(f"/api/v1/runs/{run_id}/tool-calls").text)
    return {
        "status": current.get("status"),
        "summary": _scrub(str(current.get("resultSummary") or ""))[:500],
        "error": current.get("error"),
        "runId": run_id,
        "calls": calls[:2500],
    }


def _chat(client: httpx.Client, agent_id: str, text: str) -> dict[str, Any]:
    conversation = _body(
        client.post("/api/v1/conversations", json={"agentId": agent_id, "modelAlias": ALIAS})
    )
    posted = _body(
        client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"text": text},
        )
    )
    run = posted.get("run")
    if not isinstance(run, dict):
        raise SystemExit("no run")
    return _wait(client, str(run["id"]))


def _budget(tokens: int = 16000) -> dict[str, int]:
    return {
        "maxSteps": 8,
        "maxToolCalls": 6,
        "maxWallClockS": 180,
        "maxCostMicros": 5_000_000,
        "maxTokens": tokens,
    }


def main() -> None:
    stamp = str(int(time.time()))
    admin = _client()
    evidence: dict[str, Any] = {}
    files = _publish(
        admin,
        f"m31-files-{stamp}",
        "Files",
        {
            "instructions": "Use the workspace tools exactly as asked. Quote the file text.",
            "model": {"alias": ALIAS},
            "tools": [
                {
                    "server": "general",
                    "version": "*",
                    "include": ["write_file", "list_files", "read_file", "shell", "fetch"],
                    "overrides": {"fetch": {"allowHosts": ["example.com"]}},
                }
            ],
            "budget": _budget(),
        },
    )
    evidence["files"] = _chat(
        admin,
        files,
        "Do these tool calls in order. "
        "write_file path /workspace/note.txt content 'workspace note alpha'. "
        "list_files path /workspace. "
        "read_file path /workspace/note.txt. "
        "shell command printf 'shell-ok\\n'. "
        "fetch url https://example.com/. "
        "Then quote the file text and the page title.",
    )
    child = {
        "instructions": "Reply with exactly the one word in the task. No other words.",
        "model": {"alias": ALIAS},
        "budget": _budget(4000),
    }
    _publish(admin, f"red2-{stamp}", "Red", child)
    _publish(admin, f"blue2-{stamp}", "Blue", child)
    parent = _publish(
        admin,
        f"lead2-{stamp}",
        "Lead",
        {
            "instructions": (
                "Call agents_parallel once. Ask red to reply RED and blue to reply BLUE. "
                "Then answer exactly: RED and BLUE."
            ),
            "model": {"alias": ALIAS},
            "subagents": {
                "allowed": [f"red2-{stamp}", f"blue2-{stamp}"],
                "maxDepth": 2,
                "maxParallel": 2,
                "childTimeoutS": 90,
            },
            "budget": _budget(),
        },
    )
    parallel = _chat(
        admin,
        parent,
        "Use agents_parallel for red and blue, then combine their one-word answers.",
    )
    kids = _items(admin, f"/api/v1/runs/{parallel['runId']}/children")
    evidence["parallel"] = {
        "status": parallel.get("status"),
        "summary": parallel.get("summary"),
        "children": [{"slug": row.get("agentSlug"), "status": row.get("status")} for row in kids],
    }
    asker = _publish(
        admin,
        f"ask2-{stamp}",
        "Asker",
        {
            "instructions": (
                "Your first action is agents_ask with kind approval, question 'Ship it?', "
                "and no assignee. Quote the tool error exactly. "
                "Your second action is agents_ask with kind question, question 'Which colour?', "
                "options blue and red. After the person answers, reply with that word only."
            ),
            "model": {"alias": ALIAS},
            "human": {"enabled": True},
            "budget": _budget(),
        },
    )
    asked = _chat(admin, asker, "Ask for self-approval, then ask which colour.")
    inbox = _items(admin, "/api/v1/inbox")
    question = next((row for row in inbox if row.get("runId") == asked["runId"]), None)
    denied: dict[str, Any] = {}
    answered: dict[str, Any] = {}
    if question is not None:
        if question.get("kind") == "approval":
            response = admin.post(
                f"/api/v1/inbox/{question['id']}:answer",
                json={"text": "approve"},
            )
            denied = {"status": response.status_code, "body": _scrub(response.text)[:400]}
        else:
            _body(admin.post(f"/api/v1/inbox/{question['id']}:answer", json={"text": "blue"}))
            answered = _wait(admin, str(asked["runId"]))
    evidence["ask"] = {
        "status": asked.get("status"),
        "summary": asked.get("summary"),
        "calls": asked.get("calls"),
        "question": None
        if question is None
        else {"kind": question.get("kind"), "text": question.get("question")},
        "denied": denied,
        "answered": answered.get("summary"),
    }
    approvals = _items(admin, "/api/v1/approvals")
    approver = _client("approver@dev.local")
    approver_rows = _items(approver, "/api/v1/approvals")
    evidence["approvals"] = {
        "admin": [
            {
                "id": row.get("id"),
                "name": row.get("qualifiedName") or row.get("tool"),
                "status": row.get("status"),
            }
            for row in approvals
        ],
        "approver": [
            {
                "id": row.get("id"),
                "name": row.get("qualifiedName") or row.get("tool"),
                "status": row.get("status"),
                "argsHash": row.get("argsHash"),
            }
            for row in approver_rows
        ],
    }
    text = _scrub(json.dumps(evidence, indent=2))
    path = "/tmp/m31-proof/followup.json"
    open(path, "w").write(text)
    print(text[:8000])


if __name__ == "__main__":
    main()
