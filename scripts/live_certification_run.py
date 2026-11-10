"""Steps for a live certification. The scorecard is live only when every step passes."""

from __future__ import annotations

import mimetypes
import os
import subprocess
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


def run_live(*, api: str, web: str, out: Path) -> dict[str, object]:
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
