"""Steps for a live certification. The scorecard is live only when every step passes."""

from __future__ import annotations

import importlib.util
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


def _sign_in():
    path = Path(__file__).with_name("sign_in.py")
    spec = importlib.util.spec_from_file_location("cert_sign_in", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("scripts/sign_in.py is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SIGN_IN = _sign_in()
_EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"
_CHAT_ALIASES = ("chat", "reasoning", "fast", "vision")


def _session_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Cookie plus ``X-CSRF-Token``. Mutating session calls need both."""
    pairs = [f"{name}={value}" for name, value in cookies.items() if value]
    headers = {"cookie": "; ".join(pairs)}
    token = cookies.get("ar_csrf", "")
    if token:
        headers["x-csrf-token"] = token
    return headers


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


def _still_login(page: object) -> bool:
    url = str(getattr(page, "url", "") or "")
    return "/login" in url


def _shot(page: object, path: Path, *, signed_in: bool) -> str | None:
    page.screenshot(path=str(path), full_page=True)  # type: ignore[attr-defined]
    if signed_in and _still_login(page):
        return f"{path.name} is still the sign-in page"
    return None


def _screenshots(web: str, email: str, password: str, out: Path) -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return {"ok": False, "error": "playwright is not installed"}
    shots = out / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(base_url=web)
        page.goto("/login")
        page.screenshot(path=str(shots / "01-login.png"), full_page=True)
        page.fill("#email", email)
        page.fill("#password", password)
        page.locator("form button[type=submit]").click()
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
        except Exception as exc:  # noqa: BLE001 - a stuck login is a failed screenshot
            problems.append(f"login did not leave /login ({type(exc).__name__})")
        home = _shot(page, shots / "02-home.png", signed_in=True)
        if home:
            problems.append(home)
        for name, path in (
            ("03-builder.png", "/agents/new"),
            ("04-documents.png", "/documents"),
            ("05-approvals.png", "/approvals"),
        ):
            page.goto(path)
            try:
                page.wait_for_url(lambda url: "/login" not in url, timeout=10000)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{name} returned to /login ({type(exc).__name__})")
            failed = _shot(page, shots / name, signed_in=True)
            if failed:
                problems.append(failed)
        # There is no /audit page. The audit proof is the API plus verify_audit_chain.py.
        browser.close()
    if problems:
        return {"ok": False, "error": "; ".join(problems), "dir": str(shots)}
    return {"ok": True, "dir": str(shots)}


def _upload(api: str, headers: dict[str, str], path: Path) -> tuple[int, object]:
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
        headers={
            **headers,
            "content-type": f"multipart/form-data; boundary={boundary}",
        },
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
    try:
        cookies = _SIGN_IN.sign_in(api, email, password)
    except _SIGN_IN.SignInError:
        cookies = {}
    steps.append(
        {"step": "login", "ok": bool(cookies.get("ar_session")) and bool(cookies.get("ar_csrf"))}
    )
    auth = _session_headers(cookies)
    _register_models(api, auth)
    if document.is_file() and cookies.get("ar_session"):
        upload_status, uploaded = _upload(api, auth, document)
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
    try:
        second_cookies = _SIGN_IN.sign_in(api, second_email, second_password)
    except _SIGN_IN.SignInError:
        second_cookies = {}
    steps.append(
        {
            "step": "second-user",
            "ok": bool(second_cookies.get("ar_session")) and bool(second_cookies.get("ar_csrf")),
        }
    )
    audit_status, _headers, audit = _json("GET", f"{api}/api/v1/audit-events", {}, auth)
    steps.append({"step": "audit-api", "ok": audit_status == 200})
    tenant_id = _tenant_id(api, auth, audit)
    verify_cmd = ["uv", "run", "python", "scripts/verify_audit_chain.py"]
    if tenant_id:
        verify_cmd.extend(["--tenant", tenant_id])
    verify = subprocess.run(  # noqa: S603 - argv is the fixed verifier plus one tenant id
        verify_cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    steps.append(
        {
            "step": "audit-chain",
            "ok": bool(tenant_id) and verify.returncode == 0,
            "tenantId": tenant_id,
        }
    )
    steps.extend(_stage10(api, auth))
    steps.extend(_stage11())
    _seal(steps)
    counts = _counts(steps)
    ok = counts["fail"] == 0 and counts["unverified"] == 0 and counts["pass"] > 0
    return {
        "label": "live" if ok else "contract",
        "ok": ok,
        "live": "passed" if ok else "failed",
        "modelId": model,
        "date": datetime.now(UTC).date().isoformat(),
        "counts": counts,
        "steps": steps,
        "screenshots": shots.get("dir", ""),
        "audit": audit if isinstance(audit, dict) else {},
        "notes": [
            "There is no /audit page. The audit proof is GET /api/v1/audit-events "
            "and scripts/verify_audit_chain.py --tenant.",
        ],
    }


def _poll_research(
    api: str, auth: dict[str, str], research_status: int, research: object
) -> dict[str, object]:
    """Wait until the run is terminal. Failed, timed out and still running stay distinct."""
    timeout = _seconds("AR_RESEARCH_POLL_TIMEOUT_S", 180.0)
    interval = _seconds("AR_RESEARCH_POLL_INTERVAL_S", 2.0)
    outcome = "running"
    if research_status not in {200, 202} or not isinstance(research, dict):
        return {
            "step": "research",
            "ok": False,
            "result": "fail",
            "outcome": "failed",
            "body": research,
        }
    run_raw = research.get("runId") or research.get("run_id")
    if not run_raw:
        return {
            "step": "research",
            "ok": False,
            "result": "fail",
            "outcome": "failed",
            "body": research,
        }
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        got, _headers, body = _json("GET", f"{api}/api/v1/research/runs/{run_raw}", {}, auth)
        if got == 200 and isinstance(body, dict):
            research = body
            status = str(body.get("status") or "")
            if status in {"completed", "budget_exceeded"}:
                sources = body.get("sources")
                outcome = (
                    "pass"
                    if isinstance(sources, list)
                    and sources
                    and all(
                        isinstance(row, dict) and row.get("sha256") and row.get("fetchedAt")
                        for row in sources
                    )
                    else "failed"
                )
                break
            if status in {"failed", "cancelled"}:
                outcome = "failed"
                break
        time.sleep(interval)
    else:
        outcome = "timeout"
    passed = outcome == "pass"
    return {
        "step": "research",
        "ok": passed,
        "result": "pass" if passed else "fail",
        "outcome": outcome,
        "body": research,
    }


def _seconds(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _stage10(api: str, auth: dict[str, str]) -> list[dict[str, object]]:
    """Research, the live eval sample, and the model-route read. No key is stored."""
    steps: list[dict[str, object]] = []
    research_status, _headers, research = _json(
        "POST",
        f"{api}/api/v1/research/runs",
        {"question": "What do the stored notes say about a kite?"},
        auth,
    )
    research_step = _poll_research(api, auth, research_status, research)
    steps.append(research_step)
    eval_run = subprocess.run(
        ["uv", "run", "python", "scripts/eval_run.py", "--live"],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    eval_ok = False
    eval_body: object = {"stderr": eval_run.stderr[-400:]}
    if eval_run.stdout.strip():
        try:
            eval_body = orjson.loads(eval_run.stdout)
        except orjson.JSONDecodeError:
            eval_body = {"raw": eval_run.stdout[-400:]}
    if isinstance(eval_body, dict):
        summary = eval_body.get("summary")
        rate = summary.get("pass_rate") if isinstance(summary, dict) else None
        errors = summary.get("errors") if isinstance(summary, dict) else None
        cases = eval_body.get("cases")
        every_errored = (
            isinstance(cases, int)
            and cases > 0
            and isinstance(errors, (int, float))
            and errors >= cases
        )
        eval_ok = (
            eval_run.returncode == 0
            and eval_body.get("label") == "live"
            and bool(eval_body.get("modelId"))
            and not every_errored
            and isinstance(rate, (int, float))
            and float(rate) > 0
        )
    steps.append(
        {
            "step": "eval-live",
            "ok": eval_ok,
            "result": "pass" if eval_ok else "fail",
            "body": eval_body,
        }
    )
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
                "result": "skipped-no-token",
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
            "ok": chart_status == 200 and figure,
            "result": "pass" if chart_status == 200 and figure else "unverified",
            "figure": figure,
            "proof": "live" if figure else "unverified",
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
            steps.append(
                {
                    "step": name,
                    "ok": True,
                    "pending": True,
                    "result": "skipped-no-token",
                    "proof": "contract",
                }
            )
            continue
        steps.append(_probe(name, os.environ.get(env_name, ""), url))
    rest = os.environ.get("AR_CERT_REST_TOKEN", "")
    rest_url = os.environ.get("AR_CERT_REST_URL", "")
    if not rest or not rest_url:
        steps.append(
            {
                "step": "connector-rest",
                "ok": True,
                "pending": True,
                "result": "skipped-no-token",
                "proof": "contract",
            }
        )
    else:
        steps.append(_probe("connector-rest", rest, rest_url))
    for name, env_name in (
        ("ocr-google", "AR_CERT_OCR_GOOGLE"),
        ("ocr-aws", "AR_CERT_OCR_AWS"),
        ("ocr-azure", "AR_CERT_OCR_AZURE"),
    ):
        endpoint = os.environ.get(env_name, "").strip()
        if not endpoint:
            steps.append(
                {
                    "step": name,
                    "ok": True,
                    "pending": True,
                    "result": "skipped-no-token",
                    "proof": "contract",
                }
            )
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
        steps.append(
            {
                "step": "greenmail",
                "ok": True,
                "pending": True,
                "result": "skipped-no-token",
                "proof": "contract",
            }
        )
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


def _seal(steps: list[dict[str, object]]) -> None:
    """Give every step one of pass, fail, skipped-no-token or unverified."""
    for step in steps:
        if step.get("result") in {"pass", "fail", "skipped-no-token", "unverified"}:
            step["ok"] = step["result"] == "pass"
            continue
        if step.get("pending") is True:
            step["result"] = "skipped-no-token"
        elif step.get("ok") is True:
            step["result"] = "pass"
        else:
            step["result"] = "fail"
        step["ok"] = step["result"] == "pass"


def _counts(steps: list[dict[str, object]]) -> dict[str, int]:
    names = ("pass", "fail", "skipped-no-token", "unverified")
    return {name: sum(1 for step in steps if step.get("result") == name) for name in names}


def _tenant_id(api: str, auth: dict[str, str], audit: object) -> str:
    status, _headers, session = _json("GET", f"{api}/api/v1/auth/session", {}, auth)
    if status == 200 and isinstance(session, dict):
        tenant = session.get("tenant")
        if isinstance(tenant, dict) and tenant.get("id"):
            return str(tenant["id"])
    if isinstance(audit, dict):
        items = audit.get("items")
        if (
            isinstance(items, list)
            and items
            and isinstance(items[0], dict)
            and items[0].get("tenantId")
        ):
            return str(items[0]["tenantId"])
    return ""


def _items(body: object) -> list[dict[str, object]]:
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    if isinstance(body, dict):
        found = body.get("items") or body.get("data") or []
        if isinstance(found, list):
            return [row for row in found if isinstance(row, dict)]
    return []


def _register_models(api: str, auth: dict[str, str]) -> None:
    """Register the chat model and a real embedding alias. Missing embed is a failed retrieval."""
    if not auth.get("cookie"):
        return
    base = os.environ.get("AR_LLM_BASE_URL", "https://api.deepinfra.com/v1/openai").rstrip("/")
    chat_model = os.environ.get("AR_LLM_MODEL", "Qwen/Qwen3-32B")
    embed_model = os.environ.get("AR_EMBED_MODEL", _EMBED_MODEL)
    key = os.environ.get("AR_LLM_API_KEY", "").strip()
    _status, _headers, providers = _json("GET", f"{api}/api/v1/model-providers", {}, auth)
    provider = next((row for row in _items(providers) if row.get("name") == "cert-provider"), None)
    if provider is None:
        _status, _headers, created = _json(
            "POST",
            f"{api}/api/v1/model-providers",
            {
                "name": "cert-provider",
                "kind": "openai_compatible",
                "baseUrl": base,
                "apiKey": key,
            },
            auth,
        )
        provider = created if isinstance(created, dict) else None
    if not isinstance(provider, dict) or not provider.get("id"):
        return
    _status, _headers, models = _json("GET", f"{api}/api/v1/models", {}, auth)
    rows = _items(models)

    def ensure(name: str, upstream: str, kind: str, dimensions: int | None) -> str:
        found = next((row for row in rows if row.get("upstreamModel") == upstream), None)
        if found is None:
            body: dict[str, object] = {
                "providerId": provider["id"],
                "name": name,
                "upstreamModel": upstream,
                "kind": kind,
            }
            if dimensions is not None:
                body["embeddingDimensions"] = dimensions
            _made, _headers, created = _json("POST", f"{api}/api/v1/models", body, auth)
            if isinstance(created, dict) and created.get("id"):
                rows.append(created)
                return str(created["id"])
            return ""
        return str(found.get("id") or "")

    chat_id = ensure("Qwen3-32B", chat_model, "chat", None)
    embed_id = ensure("Qwen3-Embedding-8B", embed_model, "embedding", 1024)
    _status, _headers, aliases = _json("GET", f"{api}/api/v1/model-aliases", {}, auth)
    known = {str(row.get("alias")) for row in _items(aliases)}
    if chat_id:
        for alias in _CHAT_ALIASES:
            if alias in known:
                continue
            _json(
                "POST",
                f"{api}/api/v1/model-aliases",
                {"alias": alias, "kind": "chat", "primaryModelId": chat_id},
                auth,
            )
    if embed_id and "embed" not in known:
        _json(
            "POST",
            f"{api}/api/v1/model-aliases",
            {"alias": "embed", "kind": "embedding", "primaryModelId": embed_id},
            auth,
        )


def _probe(name: str, token: str, url: str) -> dict[str, object]:
    if not token.strip():
        return {
            "step": name,
            "ok": True,
            "pending": True,
            "result": "skipped-no-token",
            "proof": "contract",
        }
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
