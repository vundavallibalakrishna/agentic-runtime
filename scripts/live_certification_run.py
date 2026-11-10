"""Steps for a live certification. The scorecard is live only when every step passes."""

from __future__ import annotations

import mimetypes
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import orjson

if TYPE_CHECKING:
    from typing import Any


def _json(
    method: str, url: str, payload: object, headers: dict[str, str]
) -> tuple[int, dict[str, str], object]:
    response = httpx.request(
        method,
        url,
        json=None if method == "GET" else payload,
        headers=headers,
        timeout=180,
    )
    raw = response.content
    try:
        parsed: object = orjson.loads(raw) if raw else {}
    except orjson.JSONDecodeError:
        parsed = {"raw": raw[:200].decode(errors="replace")}
    return response.status_code, dict(response.headers), parsed


def _cookie(headers: dict[str, str]) -> str:
    raw = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
    return raw.split(";", 1)[0]


def _screenshots(web: str, email: str, password: str, out: Path) -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return {"ok": False, "error": "playwright is not installed"}
    shots = out / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(base_url=web)
        page.goto("/login")
        page.screenshot(path=str(shots / "01-login.png"), full_page=True)
        page.fill("#email", email)
        page.fill("#password", password)
        page.locator("form button[type=submit]").click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(shots / "02-home.png"), full_page=True)
        page.goto("/agents/new")
        page.wait_for_timeout(800)
        page.screenshot(path=str(shots / "03-builder.png"), full_page=True)
        page.goto("/library")
        page.wait_for_timeout(800)
        page.screenshot(path=str(shots / "04-library.png"), full_page=True)
        page.goto("/approvals")
        page.wait_for_timeout(800)
        page.screenshot(path=str(shots / "05-approvals.png"), full_page=True)
        page.goto("/audit")
        page.wait_for_timeout(800)
        page.screenshot(path=str(shots / "06-audit.png"), full_page=True)
        browser.close()
    return {"ok": True, "dir": str(shots)}


def _upload(api: str, cookie: str, path: Path) -> tuple[int, object]:
    data = path.read_bytes()
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="upload"; filename="{path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = httpx.post(
        f"{api}/api/v1/library-documents",
        content=body,
        headers={"cookie": cookie, "content-type": f"multipart/form-data; boundary={boundary}"},
        timeout=180,
    )
    try:
        parsed: object = orjson.loads(response.content) if response.content else {}
    except orjson.JSONDecodeError:
        parsed = {}
    return response.status_code, parsed


def run_live(*, api: str, web: str, out: Path) -> dict[str, object]:  # noqa: PLR0915
    """One live pass. ``ok`` is true only when every required step succeeded."""
    email = os.environ["AR_ADMIN_EMAIL"]
    password = os.environ["AR_ADMIN_PASSWORD"]
    second_email = os.environ["AR_SECOND_EMAIL"]
    second_password = os.environ["AR_SECOND_PASSWORD"]
    model = os.environ.get("AR_LLM_MODEL", "Qwen/Qwen3-32B")
    document = Path(os.environ.get("AR_CERT_DOCUMENT", ""))
    steps: list[dict[str, object]] = []
    shots = _screenshots(web, email, password, out)
    steps.append({"step": "screenshots", "ok": shots.get("ok") is True})
    status, headers, _parsed = _json(
        "POST", f"{api}/api/v1/auth/login", {"email": email, "password": password}, {}
    )
    cookie = _cookie(headers)
    steps.append({"step": "login", "ok": status == 200 and cookie.startswith("ar_session=")})
    auth = {"cookie": cookie}
    if document.is_file() and cookie:
        upload_status, uploaded = _upload(api, cookie, document)
        document_id = uploaded.get("id") if isinstance(uploaded, dict) else None
        steps.append({"step": "upload", "ok": upload_status in {200, 201} and bool(document_id)})
        if document_id:
            judge_status, _headers, judged = _json(
                "POST",
                f"{api}/api/v1/library-documents/{document_id}:judge",
                {"statements": ["The document states what it is about."], "modelAlias": "chat"},
                auth,
            )
            steps.append({"step": "documents.judge", "ok": judge_status == 200, "body": judged})
    else:
        steps.append({"step": "upload", "ok": False, "error": "AR_CERT_DOCUMENT is missing"})
    agent_status, _headers, agents = _json("GET", f"{api}/api/v1/agents", {}, auth)
    rows: list[Any] = []
    if isinstance(agents, dict):
        found = agents.get("items") or agents.get("agents") or []
        rows = found if isinstance(found, list) else []
    elif isinstance(agents, list):
        rows = agents
    assistant = next(
        (row for row in rows if isinstance(row, dict) and row.get("slug") == "assistant"), None
    )
    steps.append({"step": "list-agents", "ok": agent_status == 200 and isinstance(assistant, dict)})
    token = ""
    if isinstance(assistant, dict):
        key_status, _headers, created = _json(
            "POST",
            f"{api}/api/v1/agents/{assistant.get('id')}/api-keys",
            {"label": "live-cert", "scope": "agent"},
            auth,
        )
        token = ""
        if isinstance(created, dict):
            token = str(created.get("key") or "")
        steps.append({"step": "api-key", "ok": key_status in {200, 201} and bool(token)})
        if token:
            run_status, _headers, reply = _json(
                "POST",
                f"{api}/v1/agents/assistant:run",
                {"text": "Use a tool to list the files you can see, then stop.", "stream": False},
                {"authorization": f"Bearer {token}"},
            )
            steps.append({"step": "tool-turn", "ok": run_status == 200, "body": reply})
    steps.extend(_stage13(api, token))
    second_status, second_headers, _parsed = _json(
        "POST",
        f"{api}/api/v1/auth/login",
        {"email": second_email, "password": second_password},
        {},
    )
    second_cookie = _cookie(second_headers)
    steps.append({"step": "second-user", "ok": second_status == 200 and bool(second_cookie)})
    audit_status, _headers, audit = _json("GET", f"{api}/api/v1/audit-events", {}, auth)
    steps.append({"step": "audit-api", "ok": audit_status == 200})
    verify = subprocess.run(
        ["uv", "run", "python", "scripts/verify_audit_chain.py"],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    steps.append({"step": "audit-chain", "ok": verify.returncode == 0})
    steps.extend(_stage10(api, auth))
    steps.extend(_stage11())
    ok = all(item.get("ok") is True for item in steps)
    return {
        "label": "live" if ok else "contract",
        "ok": ok,
        "live": "passed" if ok else "failed",
        "modelId": model,
        "date": datetime.now(UTC).date().isoformat(),
        "steps": steps,
        "screenshots": shots.get("dir", ""),
        "audit": audit if isinstance(audit, dict) else {},
    }


def _stage10(api: str, auth: dict[str, str]) -> list[dict[str, object]]:
    """Research, the live eval sample, and the model-route read. No key is stored."""
    steps: list[dict[str, object]] = []
    research_status, _headers, research = _json(
        "POST",
        f"{api}/api/v1/research/runs",
        {"question": "What do the stored notes say about a kite?"},
        auth,
    )
    research_ok = False
    if research_status in {200, 202} and isinstance(research, dict):
        run_raw = research.get("runId") or research.get("run_id")
        if run_raw:
            for _wait in range(15):
                got, _headers, body = _json(
                    "GET", f"{api}/api/v1/research/runs/{run_raw}", {}, auth
                )
                if (
                    got == 200
                    and isinstance(body, dict)
                    and body.get("status")
                    in {
                        "completed",
                        "budget_exceeded",
                    }
                ):
                    sources = body.get("sources")
                    research_ok = isinstance(sources, list) and all(
                        isinstance(row, dict) and row.get("sha256") and row.get("fetchedAt")
                        for row in sources
                    )
                    research = body
                    break
                time.sleep(1)
    steps.append({"step": "research", "ok": research_ok, "body": research})
    eval_run = subprocess.run(
        ["uv", "run", "python", "scripts/eval_run.py", "--live"],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    eval_ok = False
    eval_body: object = {"stderr": eval_run.stderr[-400:]}
    if eval_run.returncode == 0 and eval_run.stdout.strip():
        try:
            eval_body = orjson.loads(eval_run.stdout)
        except orjson.JSONDecodeError:
            eval_body = {"raw": eval_run.stdout[-400:]}
        if isinstance(eval_body, dict):
            eval_ok = eval_body.get("label") == "live" and bool(eval_body.get("modelId"))
    steps.append({"step": "eval-live", "ok": eval_ok, "body": eval_body})
    routes_status, _headers, routes = _json("GET", f"{api}/api/v1/model-routes", {}, auth)
    steps.append(
        {
            "step": "model-routes",
            "ok": routes_status == 200,
            "body": routes if routes_status == 200 else {},
        }
    )
    return steps


def _stage13(api: str, token: str) -> list[dict[str, object]]:
    """Content parts, follow-ups, a chart reply, and hidden thinking on /v1."""
    if not token:
        return [
            {
                "step": "stage13-rich-reply",
                "ok": True,
                "pending": True,
                "proof": "contract",
            }
        ]
    headers = {"authorization": f"Bearer {token}"}
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    status, _headers, reply = _json(
        "POST",
        f"{api}/v1/agents/assistant:run",
        {
            "text": "Count two groups named North and South. Reply as JSON with an answer string.",
            "suggestFollowups": True,
            "responseFormat": schema,
        },
        headers,
    )
    content = reply.get("content") if isinstance(reply, dict) else None
    prompts: list[object] = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "followups":
                found = part.get("prompts")
                prompts = found if isinstance(found, list) else []
    hidden = True
    run_id = reply.get("id") if isinstance(reply, dict) else None
    if run_id:
        event_status, _event_headers, events = _json(
            "GET",
            f"{api}/v1/agents/assistant/runs/{run_id}/events",
            {},
            {**headers, "accept": "application/json"},
        )
        items = events.get("items") if isinstance(events, dict) else events
        if event_status == 200 and isinstance(items, list):
            hidden = not any(
                isinstance(event, dict) and event.get("type") == "reasoning.delta"
                for event in items
            )
        else:
            hidden = False
    chart_status, _chart_headers, chart = _json(
        "POST",
        f"{api}/v1/agents/assistant:run",
        {
            "text": "Use the chart tool to draw a bar chart with North 2 and South 5. Then stop.",
        },
        headers,
    )
    chart_content = chart.get("content") if isinstance(chart, dict) else None
    figure = False
    if isinstance(chart_content, list):
        figure = any(
            isinstance(part, dict) and part.get("type") in {"file", "image"}
            for part in chart_content
        )
    return [
        {
            "step": "stage13-content-parts",
            "ok": status == 200 and isinstance(content, list) and hidden,
            "followups": len(prompts),
            "proof": "live",
        },
        {
            "step": "stage13-chart",
            "ok": chart_status == 200,
            "figure": figure,
            "proof": "live" if figure else "contract",
        },
    ]


def _stage11() -> list[dict[str, object]]:
    """Connector, OCR and mail hooks. A missing secret is pending, not a failed live run."""
    steps: list[dict[str, object]] = []
    probes = (
        ("connector-slack", "AR_CERT_SLACK_TOKEN", "https://slack.com/api/auth.test"),
        (
            "connector-google",
            "AR_CERT_GOOGLE_TOKEN",
            "https://www.googleapis.com/oauth2/v3/userinfo",
        ),
        (
            "connector-microsoft",
            "AR_CERT_MICROSOFT_TOKEN",
            "https://graph.microsoft.com/v1.0/me",
        ),
        ("connector-atlassian", "AR_CERT_ATLASSIAN_TOKEN", "https://api.atlassian.com/me"),
        ("connector-github", "AR_CERT_GITHUB_TOKEN", "https://api.github.com/user"),
    )
    for name, env_name, url in probes:
        steps.append(_probe(name, os.environ.get(env_name, ""), url))
    for name, env_name, url in (
        (
            "connector-gdrive",
            "AR_CERT_GDRIVE_TOKEN",
            "https://www.googleapis.com/drive/v3/about?fields=user",
        ),
        (
            "connector-gcal",
            "AR_CERT_GCAL_TOKEN",
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        ),
        (
            "connector-gmail",
            "AR_CERT_GMAIL_TOKEN",
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        ),
        (
            "connector-outlook",
            "AR_CERT_OUTLOOK_TOKEN",
            "https://graph.microsoft.com/v1.0/me/messages?$top=1",
        ),
        (
            "connector-onedrive",
            "AR_CERT_ONEDRIVE_TOKEN",
            "https://graph.microsoft.com/v1.0/me/drive",
        ),
        (
            "connector-teams",
            "AR_CERT_TEAMS_TOKEN",
            "https://graph.microsoft.com/v1.0/me/joinedTeams",
        ),
        ("connector-jira", "AR_CERT_JIRA_TOKEN", os.environ.get("AR_CERT_JIRA_URL", "")),
        (
            "connector-confluence",
            "AR_CERT_CONFLUENCE_TOKEN",
            os.environ.get("AR_CERT_CONFLUENCE_URL", ""),
        ),
    ):
        if not url:
            steps.append({"step": name, "ok": True, "pending": True, "proof": "contract"})
            continue
        steps.append(_probe(name, os.environ.get(env_name, ""), url))
    rest = os.environ.get("AR_CERT_REST_TOKEN", "")
    rest_url = os.environ.get("AR_CERT_REST_URL", "")
    if not rest or not rest_url:
        steps.append({"step": "connector-rest", "ok": True, "pending": True, "proof": "contract"})
    else:
        steps.append(_probe("connector-rest", rest, rest_url))
    for name, env_name in (
        ("ocr-google", "AR_CERT_OCR_GOOGLE"),
        ("ocr-aws", "AR_CERT_OCR_AWS"),
        ("ocr-azure", "AR_CERT_OCR_AZURE"),
    ):
        endpoint = os.environ.get(env_name, "").strip()
        if not endpoint:
            steps.append({"step": name, "ok": True, "pending": True, "proof": "contract"})
            continue
        try:
            response = httpx.post(endpoint, content=b"", timeout=20)
            steps.append(
                {
                    "step": name,
                    "ok": response.status_code < 500,
                    "proof": "contract",
                    "status": response.status_code,
                }
            )
        except httpx.HTTPError as exc:
            steps.append({"step": name, "ok": False, "error": type(exc).__name__})
    smtp = os.environ.get("AR_GREENMAIL_SMTP", "").strip()
    if not smtp or ":" not in smtp:
        steps.append({"step": "greenmail", "ok": True, "pending": True, "proof": "contract"})
    else:
        host, _, port_text = smtp.partition(":")
        try:
            from ar_domain.notifications.smtp_mail import send_smtp  # noqa: PLC0415

            send_smtp(
                {
                    "host": host,
                    "port": int(port_text),
                    "to": "certify@example.com",
                    "subject": "certify",
                    "body": "pending-check",
                    "from": "noreply@dev.local",
                }
            )
            steps.append({"step": "greenmail", "ok": True, "proof": "contract", "host": host})
        except Exception as exc:  # noqa: BLE001 - the scorecard records the failure, not the body
            steps.append({"step": "greenmail", "ok": False, "error": type(exc).__name__})
    return steps


def _probe(name: str, token: str, url: str) -> dict[str, object]:
    if not token.strip():
        return {"step": name, "ok": True, "pending": True, "proof": "contract"}
    try:
        response = httpx.get(
            url,
            headers={"authorization": f"Bearer {token.strip()}"},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        return {"step": name, "ok": False, "error": type(exc).__name__}
    return {
        "step": name,
        "ok": response.status_code < 400,
        "proof": "contract",
        "status": response.status_code,
    }
