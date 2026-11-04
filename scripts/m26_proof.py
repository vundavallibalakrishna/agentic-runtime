"""Live proof for the connector catalog.

The model key is read from AR_CERT_LLM_API_KEY and is never printed.
A GitHub token, when present, is read from `gh auth token` and scrubbed
from the evidence file.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import httpx
import orjson

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18127")
S3_ENDPOINT = os.environ.get("AR_PROOF_S3", "http://127.0.0.1:18333")
SMTP_HOST = os.environ.get("AR_PROOF_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("AR_PROOF_SMTP_PORT", "11025"))
MAILPIT = os.environ.get("AR_PROOF_MAILPIT", "http://127.0.0.1:18025")
OUT = Path(os.environ.get("AR_PROOF_OUT", "/tmp/m26-proof"))  # noqa: S108
S3_KEY = "m26access"
S3_SECRET = "m26secretkey"  # noqa: S105
BUCKET = "m26proof"


def _gh_token() -> str:
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def _scrub(text: str) -> str:
    secrets = [
        os.environ.get("AR_CERT_LLM_API_KEY", ""),
        _gh_token(),
        S3_SECRET,
    ]
    for secret in secrets:
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
    body = _json(client.get(path))
    rows = body.get("items")
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


def _approve_if_needed(client: httpx.Client, result: dict[str, object]) -> dict[str, object]:
    if result.get("status") != "awaiting_approval":
        return result
    approval_id = str(result.get("approvalId") or "")
    args_hash = str(result.get("argsHash") or "")
    if not approval_id:
        return result
    decided = _json(
        client.post(
            f"/api/v1/approvals/{approval_id}:decide",
            json={"decision": "approve", "argsHash": args_hash, "comment": "proof"},
        )
    )
    return {"approved": True, "decision": decided.get("status"), "before": result.get("status")}


def _setup_model(client: httpx.Client) -> None:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("AR_CERT_LLM_API_KEY is missing")
    aliases = _items(client, "/api/v1/model-aliases")
    if any(row.get("alias") == "qwenm26" for row in aliases):
        return
    provider = _json(
        client.post(
            "/api/v1/model-providers",
            json={
                "name": "DeepInfra M26",
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
            json={"alias": "qwenm26", "kind": "chat", "primaryModelId": chat["id"]},
        )
    )
    tested = _json(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
    if not tested.get("ok"):
        raise SystemExit("provider test failed")


def _install(client: httpx.Client) -> None:
    _json(
        client.post(
            "/api/v1/connectors/github:install",
            json={"connectionName": "github-public"},
        )
    )
    token = _gh_token()
    if token:
        _json(
            client.post(
                "/api/v1/service-connections",
                json={"name": "github-write", "kind": "bearer", "secret": token},
            )
        )
    _json(
        client.post(
            "/api/v1/connectors/s3:install",
            json={
                "connectionName": "s3-local",
                "kind": "basic",
                "username": S3_KEY,
                "secret": S3_SECRET,
                "config": {
                    "endpoint": S3_ENDPOINT,
                    "region": "us-east-1",
                    "bucket": BUCKET,
                },
            },
        )
    )
    _json(
        client.post(
            "/api/v1/connectors/email:install",
            json={
                "connectionName": "mail-local",
                "kind": "basic",
                "username": "ada@example.com",
                "secret": "local-mailbox",
                "config": {
                    "smtpHost": SMTP_HOST,
                    "smtpPort": str(SMTP_PORT),
                    "smtpTls": "false",
                    "fromAddress": "ada@example.com",
                },
            },
        )
    )


def _shape(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _shape(item) for key, item in list(value.items())[:12]}
    if isinstance(value, list):
        return [_shape(item) for item in value[:3]]
    if isinstance(value, str) and len(value) > 180:
        return value[:180]
    return value


def _ask(client: httpx.Client) -> dict[str, object]:
    agent = _json(
        client.post(
            "/api/v1/agents",
            json={
                "slug": f"m26-{int(time.time())}",
                "name": "Connector reader",
                "visibility": "private",
                "definition": {
                    "instructions": (
                        "When asked to read a GitHub file, call github_read_file "
                        "and quote the first heading from the tool result. "
                        "Do not invent the file."
                    ),
                    "model": {"alias": "qwenm26"},
                    "tools": [
                        {
                            "server": "connectors",
                            "version": "*",
                            "include": ["github_read_file", "s3_get", "email_send"],
                        }
                    ],
                    "budget": {
                        "maxSteps": 6,
                        "maxToolCalls": 4,
                        "maxWallClockS": 180,
                        "maxCostMicros": 5_000_000,
                        "maxTokens": 8000,
                    },
                },
            },
        )
    )
    _json(
        client.post(
            f"/api/v1/agents/{agent['id']}:publish",
            json={"changeNote": "proof"},
        )
    )
    conversation = _json(
        client.post(
            "/api/v1/conversations",
            json={"agentId": agent["id"], "modelAlias": "qwenm26"},
        )
    )
    posted = _json(
        client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={
                "text": (
                    "Use github_read_file with owner octocat, repo Hello-World and path README. "
                    "Quote the first heading."
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
    return {"status": status, "summary": summary[:1000]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    public = httpx.get("https://api.github.com/repos/octocat/Hello-World", timeout=30)
    public_body = public.json()
    evidence: dict[str, object] = {
        "githubPublic": {
            "status": public.status_code,
            "shape": {
                "fullName": public_body.get("full_name"),
                "private": public_body.get("private"),
                "keys": sorted(public_body)[:8],
            },
        }
    }
    client = _client()
    _setup_model(client)
    _install(client)
    read = _call(
        client,
        "github_read_file",
        {"owner": "octocat", "repo": "Hello-World", "path": "README"},
    )
    evidence["githubTool"] = {
        "status": read.get("status"),
        "error": read.get("error"),
        "text": _scrub(str(read.get("text") or ""))[:400],
    }
    token = _gh_token()
    evidence["githubTokenPresent"] = bool(token)
    if token:
        installs = _items(client, "/api/v1/connectors")
        github = next(row for row in installs if row.get("slug") == "github")
        install_id = str(github.get("installId") or "")
        _json(
            client.patch(
                f"/api/v1/connector-installs/{install_id}",
                json={"connectionName": "github-write"},
            )
        )
        created = _call(
            client,
            "github_create_issue",
            {
                "owner": "vundavallibalakrishna",
                "repo": "agentic-runtime",
                "title": "M26 connector proof",
                "body": "Created by the connector proof. Safe to close.",
            },
        )
        evidence["githubIssue"] = _approve_if_needed(client, created)
        evidence["githubIssueText"] = _scrub(str(created.get("text") or ""))[:300]
    put = _call(client, "s3_put", {"key": "proof.txt", "text": "m26 proof object"})
    evidence["s3Put"] = _approve_if_needed(client, put)
    got = _call(client, "s3_get", {"key": "proof.txt"})
    evidence["s3Get"] = {
        "status": got.get("status"),
        "text": _scrub(str(got.get("text") or ""))[:200],
    }
    sent = _call(
        client,
        "email_send",
        {
            "to": "dev@example.com",
            "subject": "M26 local proof",
            "body": "Sent through local Mailpit.",
        },
    )
    evidence["email"] = _approve_if_needed(client, sent)
    try:
        messages = urllib.request.urlopen(f"{MAILPIT}/api/v1/messages", timeout=10).read()  # noqa: S310
        evidence["mailpit"] = orjson.loads(messages)
        total = evidence["mailpit"].get("total") if isinstance(evidence["mailpit"], dict) else None
        evidence["mailpitTotal"] = total
        evidence["mailpit"] = {"total": total}
    except OSError as exc:
        evidence["mailpit"] = {"error": exc.__class__.__name__}
    evidence["chat"] = _ask(client)
    text = _scrub(json.dumps(evidence, indent=2))
    (OUT / "evidence.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
