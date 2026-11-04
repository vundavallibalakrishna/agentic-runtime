"""Live M23 proof. The provider key is read from the environment and never stored."""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import httpx
import orjson
import psycopg

BASE = os.environ.get("M23_API", "http://127.0.0.1:18123")
ROOT = Path(tempfile.gettempdir()) / "m23-proof"
CSV_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/1962_2006_walmart_store_openings.csv"
)
XLSX_URL = "https://github.com/pandas-dev/pandas/raw/main/pandas/tests/io/data/excel/test1.xlsx"
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "rows": {"type": "integer"}},
    "required": ["answer", "rows"],
    "additionalProperties": False,
}


def _scrub(text: str) -> str:
    secrets_found = [
        os.environ.get("AR_CERT_LLM_API_KEY", ""),
        os.environ.get("M23_ANALYST_PASSWORD", ""),
        "loader",
    ]
    state = ROOT / "state.json"
    if state.exists():
        saved = orjson.loads(state.read_bytes())
        secrets_found.append(str(saved.get("analystPassword") or ""))
    for secret in secrets_found:
        if secret and secret in text:
            text = text.replace(secret, "[redacted]")
    return text


def _client() -> httpx.Client:
    client = httpx.Client(base_url=BASE, timeout=180.0, follow_redirects=False)
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
        raise SystemExit(f"{response.request.method} {response.status_code} {text[:600]}")
    body = response.json()
    if not isinstance(body, dict):
        raise SystemExit("response was not an object")
    dumped = json.dumps(body)
    if os.environ.get("AR_CERT_LLM_API_KEY", "") and os.environ["AR_CERT_LLM_API_KEY"] in dumped:
        raise SystemExit("a response contained the provider key")
    return body


def _download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.write_bytes(urllib.request.urlopen(url, timeout=60).read())  # noqa: S310


def _load_customer() -> str:
    ROOT.mkdir(parents=True, exist_ok=True)
    csv_path = ROOT / "walmart.csv"
    xlsx_path = ROOT / "test1.xlsx"
    _download(CSV_URL, csv_path)
    _download(XLSX_URL, xlsx_path)
    password = secrets.token_urlsafe(18)
    os.environ["M23_ANALYST_PASSWORD"] = password
    rows = list(csv.reader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    header = [name.strip().lower() for name in rows[0]]
    columns = ", ".join(f'"{name}" text' for name in header)
    with psycopg.connect(
        "postgresql://loader:loader@127.0.0.1:55432/analysis", autocommit=True
    ) as conn:
        conn.execute("DROP TABLE IF EXISTS stores")
        conn.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst') THEN "
            "REVOKE ALL ON SCHEMA public FROM analyst; "
            "REVOKE CONNECT ON DATABASE analysis FROM analyst; "
            "DROP ROLE analyst; "
            "END IF; END $$"
        )
        conn.execute(f"CREATE TABLE stores ({columns})")
        with conn.cursor() as cursor:
            copy = "COPY stores FROM STDIN WITH (FORMAT csv, HEADER true)"
            with cursor.copy(copy) as stream:
                stream.write(csv_path.read_bytes())
        conn.execute(f"CREATE ROLE analyst LOGIN PASSWORD {password!r}")
        conn.execute("GRANT CONNECT ON DATABASE analysis TO analyst")
        conn.execute("GRANT USAGE ON SCHEMA public TO analyst")
        conn.execute("GRANT SELECT ON stores TO analyst")
        count = conn.execute("SELECT count(*) FROM stores").fetchone()
    (ROOT / "loaded.txt").write_text(
        f"rows={count[0] if count else 0}\nheader={','.join(header)}\n"
    )
    return password


def _items(client: httpx.Client, path: str) -> list[dict[str, object]]:
    body = _json(client.get(path))
    rows = body.get("items")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _setup(client: httpx.Client) -> None:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if not key:
        raise SystemExit("AR_CERT_LLM_API_KEY is missing")
    password = _load_customer()
    aliases = _items(client, "/api/v1/model-aliases")
    alias = next((row for row in aliases if row.get("alias") == "qwenm23"), None)
    if alias is None:
        provider = _json(
            client.post(
                "/api/v1/model-providers",
                json={
                    "name": "DeepInfra M23",
                    "kind": "openai_compatible",
                    "baseUrl": "https://api.deepinfra.com/v1/openai",
                    "apiKey": key,
                },
            )
        )
        model = _json(
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
        alias = _json(
            client.post(
                "/api/v1/model-aliases",
                json={"alias": "qwenm23", "kind": "chat", "primaryModelId": model["id"]},
            )
        )
        tested = _json(client.post(f"/api/v1/model-providers/{provider['id']}:test"))
        provider_id = str(provider["id"])
    else:
        provider_id = str(alias.get("providerId") or "")
        tested = {"ok": True, "reused": True}
    services = _items(client, "/api/v1/service-connections")
    service = next((row for row in services if row.get("name") == "proofapi"), None)
    if service is None:
        service = _json(
            client.post(
                "/api/v1/service-connections",
                json={"name": "proofapi", "kind": "bearer", "secret": "proof-secret-value"},
            )
        )
    servers = _items(client, "/api/v1/tool-servers")
    described: dict[str, object] = {"slug": "zen"}
    if not any(row.get("slug") == "zen" for row in servers):
        described = _json(
            client.post(
                "/api/v1/described-tools",
                json={"description": "GET https://example.com/zen", "slug": "zen"},
            )
        )
    existing = _items(client, "/api/v1/data-connections")
    for row in existing:
        if str(row.get("name") or "").lower() == "walmart":
            client.delete(f"/api/v1/data-connections/{row['id']}")
    connection = _json(
        client.post(
            "/api/v1/data-connections",
            json={
                "name": "walmart",
                "engine": "postgres",
                "dsn": f"postgresql://analyst:{password}@127.0.0.1:55432/analysis",
                "allowlist": {"schemas": ["public"], "tables": ["public.stores"]},
                "rowLimit": 1000,
                "statementTimeoutS": 30,
            },
        )
    )
    if password in json.dumps(connection) or "dsn" in connection:
        raise SystemExit("data connection view exposed the DSN")
    probe = _json(client.post(f"/api/v1/data-connections/{connection['id']}:test"))
    agents = _items(client, "/api/v1/agents")
    agent = next((row for row in agents if row.get("slug") == "analyst-m23"), None)
    if agent is None:
        agent = _json(
            client.post(
                "/api/v1/agents",
                json={
                    "slug": "analyst-m23",
                    "name": "Analyst",
                    "visibility": "private",
                    "definition": {
                        "instructions": (
                            "Answer questions about the walmart connection and uploaded files. "
                            "Use data.query. If SQL fails, list tables, then retry. "
                            "Charts use general.chart. Export with general.export_table rows. "
                            "File names may be under inputs/."
                        ),
                        "model": {"alias": "qwenm23"},
                        "tools": [
                            {
                                "server": "data",
                                "version": "*",
                                "include": [
                                    "list_schemas",
                                    "list_tables",
                                    "describe_table",
                                    "query",
                                ],
                                "overrides": {
                                    "query": {
                                        "rowLimit": 500,
                                        "schemas": ["public"],
                                        "tables": ["public.stores"],
                                    }
                                },
                            },
                            {
                                "server": "general",
                                "version": "*",
                                "include": [
                                    "inspect_table",
                                    "query_table",
                                    "export_table",
                                    "chart",
                                    "list_files",
                                ],
                            },
                        ],
                        "budget": {
                            "maxSteps": 12,
                            "maxToolCalls": 16,
                            "maxWallClockS": 180,
                            "maxCostMicros": 1000000,
                        },
                        "output": {"jsonSchema": SCHEMA},
                    },
                },
            )
        )
    published = _json(
        client.post(
            f"/api/v1/agents/{agent['id']}:publish",
            json={"changeNote": "m23 proof", "skipEvalGate": True},
        )
    )
    state = {
        "providerId": provider_id,
        "alias": alias.get("alias") or "qwenm23",
        "agentId": agent["id"],
        "connectionId": connection["id"],
        "serviceId": service["id"],
        "described": described.get("slug") or described.get("name") or "zen",
        "providerTest": tested.get("ok"),
        "probe": probe,
        "published": published.get("status") or published.get("version"),
    }
    (ROOT / "state.json").write_text(json.dumps(state, indent=2))
    _record("setup", state)


def _state() -> dict[str, object]:
    loaded = orjson.loads((ROOT / "state.json").read_bytes())
    if not isinstance(loaded, dict):
        raise SystemExit("state was not an object")
    return loaded


def _ask(
    client: httpx.Client, text: str, attachments: list[str] | None = None
) -> dict[str, object]:
    state = _state()
    posted_body: dict[str, object] = {"text": text}
    if attachments:
        posted_body["attachmentIds"] = attachments
    conversation = _json(
        client.post(
            "/api/v1/conversations", json={"agentId": state["agentId"], "modelAlias": "qwenm23"}
        )
    )
    posted = _json(
        client.post(f"/api/v1/conversations/{conversation['id']}/messages", json=posted_body)
    )
    run = posted.get("run")
    if not isinstance(run, dict):
        raise SystemExit("message did not start a run")
    run_id = str(run["id"])
    deadline = time.monotonic() + 240
    status = ""
    summary = ""
    while time.monotonic() < deadline:
        current = _json(client.get(f"/api/v1/runs/{run_id}"))
        status = str(current.get("status") or "")
        summary = _scrub(str(current.get("resultSummary") or current.get("summary") or ""))
        if status in {"completed", "failed", "waiting_approval", "budget_exceeded", "cancelled"}:
            break
        time.sleep(3)
    calls = _scrub(client.get(f"/api/v1/runs/{run_id}/tool-calls").text)
    audits = _scrub(client.get(f"/api/v1/runs/{run_id}").text)
    return {
        "status": status,
        "summary": summary[:1200],
        "calls": calls[:6000],
        "run": audits[:1500],
    }


def _record(name: str, body: object) -> None:
    path = ROOT / "evidence.json"
    current = orjson.loads(path.read_bytes()) if path.exists() else {}
    current[name] = orjson.loads(_scrub(json.dumps(body)).encode())
    path.write_text(json.dumps(current, indent=2))
    raw = path.read_text()
    key = os.environ.get("AR_CERT_LLM_API_KEY", "")
    if key and key in raw:
        raise SystemExit("evidence still contains the provider key")


def _sql(client: httpx.Client) -> None:
    result = _ask(
        client,
        "How many rows are in public.stores on walmart, and which strstate has the most? "
        "Use data.query. If SQL fails, list tables and describe the table, then retry. "
        "Draw a bar chart of the top 5 states and export those rows to top_states.xlsx. "
        'Then reply with JSON {"answer":"...","rows":<count>}.',
    )
    _record("sql", result)


def _files(client: httpx.Client) -> None:
    csv_id = _json(
        client.post(
            "/api/v1/files:upload",
            files={"upload": ("walmart.csv", (ROOT / "walmart.csv").read_bytes(), "text/csv")},
        )
    )["id"]
    xlsx_id = _json(
        client.post(
            "/api/v1/files:upload",
            files={
                "upload": (
                    "test1.xlsx",
                    (ROOT / "test1.xlsx").read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    )["id"]
    result = _ask(
        client,
        "Inspect inputs/walmart.csv and inputs/test1.xlsx. Count the CSV rows with SQL. "
        'Reply with JSON {"answer":"file summary","rows":<csv row count>}.',
        [str(csv_id), str(xlsx_id)],
    )
    _record("files", result)


def _retry(client: httpx.Client) -> None:
    result = _ask(
        client,
        "Reply with exactly the word hello and no JSON object.",
    )
    _record("retry", result)


def _drop(client: httpx.Client) -> None:
    tools = _json(client.get("/api/v1/tools"))
    items = tools.get("items")
    found = ""
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and str(item.get("qualifiedName") or item.get("name")) in {
                "data.query",
                "query",
            }:
                found = str(item.get("toolId") or item.get("id") or "")
                if str(item.get("qualifiedName")) == "data.query":
                    break
    if not found:
        raise SystemExit("data.query was not in the registry")
    result = _json(
        client.post(
            f"/api/v1/tools/{found}:test",
            json={"arguments": {"connection": "walmart", "sql": "DROP TABLE stores"}},
        )
    )
    with psycopg.connect("postgresql://loader:loader@127.0.0.1:55432/analysis") as conn:
        count = conn.execute("SELECT count(*) FROM stores").fetchone()
    _record(
        "drop", {"tool": _scrub(json.dumps(result))[:800], "rowsAfter": count[0] if count else None}
    )


def _persist(client: httpx.Client) -> None:
    data = _json(client.get("/api/v1/data-connections"))
    services = _json(client.get("/api/v1/service-connections"))
    aliases = _json(client.get("/api/v1/model-aliases"))
    tools = _json(client.get("/api/v1/tool-servers"))
    _record(
        "persist",
        {
            "databases": [
                row.get("name") for row in data.get("items", []) if isinstance(row, dict)
            ],
            "services": [
                row.get("name") for row in services.get("items", []) if isinstance(row, dict)
            ],
            "aliases": [
                row.get("alias") for row in aliases.get("items", []) if isinstance(row, dict)
            ],
            "servers": [row.get("slug") for row in tools.get("items", []) if isinstance(row, dict)],
        },
    )


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "setup"
    client = _client()
    if phase == "setup":
        _setup(client)
    elif phase == "sql":
        _sql(client)
    elif phase == "files":
        _files(client)
    elif phase == "retry":
        _retry(client)
    elif phase == "drop":
        _drop(client)
    elif phase == "persist":
        _persist(client)
    else:
        raise SystemExit(f"unknown phase {phase}")


if __name__ == "__main__":
    main()
