"""Health, dev login and Keycloak sign-in for a fresh local stack.

``make dev`` blocks on honcho, so CI runs the same steps and then this script.
Keycloak with organizations asks for the username and then the password.
"""

from __future__ import annotations

import os
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx

ROOT = Path(__file__).resolve().parents[1]
SEEDED = (
    "admin@dev.local",
    "builder@dev.local",
    "member@dev.local",
    "approver@dev.local",
)
PASSWORD = "dev-password"  # noqa: S105 - documented dev realm password


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "form":
            self._current = {"action": attr.get("action", ""), "names": [], "fields": {}}
            self.forms.append(self._current)
            return
        if tag != "input" or self._current is None:
            return
        name = attr.get("name", "")
        if not name:
            return
        names = self._current["names"]
        fields = self._current["fields"]
        if isinstance(names, list):
            names.append(name)
        if isinstance(fields, dict):
            fields[name] = attr.get("value", "")


def parse_forms(html: str) -> list[dict[str, object]]:
    """Return forms with their input names and current values."""
    parser = _FormParser()
    parser.feed(html)
    return parser.forms


def fill_login(form: dict[str, object], email: str, password: str) -> dict[str, str] | None:
    """Fill the username step, the password step, or both when they share a page."""
    names = form.get("names")
    fields = form.get("fields")
    if not isinstance(names, list) or not isinstance(fields, dict):
        return None
    if "username" not in names and "password" not in names:
        return None
    payload = {str(key): str(value) for key, value in fields.items()}
    if "username" in names and "password" not in names:
        payload["username"] = email
        return payload
    if "username" in names and not payload.get("username"):
        payload["username"] = email
    if "password" in names:
        payload["password"] = password
    return payload


def _env(name: str, default: str = "") -> str:
    if os.environ.get(name, "").strip():
        return os.environ[name].strip()
    path = ROOT / ".env"
    if not path.is_file():
        return default
    prefix = f"{name}="
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip().strip("'\"")
    return default


def _port(name: str, default: str) -> str:
    value = _env(name, default)
    return value or default


def _wait_ok(url: str, seconds: float = 180) -> None:
    deadline = time.monotonic() + seconds
    last = "not tried"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=5)
            if response.status_code == 200:
                print(f"up {url}")
                return
            last = f"{response.status_code}"
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(2)
    print(f"timed out waiting for {url}: {last}", file=sys.stderr)
    raise SystemExit(1)


def _dev_logins(api: str) -> None:
    for email in SEEDED:
        response = httpx.post(
            f"{api}/api/v1/auth/dev-login",
            data={"email": email},
            timeout=15,
            follow_redirects=False,
        )
        location = response.headers.get("location", "")
        cookie = response.headers.get("set-cookie", "")
        if (
            response.status_code != 303
            or not location.endswith("/chat")
            or "ar_session=" not in cookie
        ):
            print(
                f"dev login failed for {email}: {response.status_code} {location}", file=sys.stderr
            )
            raise SystemExit(1)
        print(f"dev login {email}")


def _ensure_org_members(keycloak: str) -> None:
    """Put the seeded users in the dev organisation so the login form can finish."""
    token = httpx.post(
        f"{keycloak}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin",
        },
        timeout=20,
    )
    if token.status_code != 200:
        print(f"keycloak admin token {token.status_code}", file=sys.stderr)
        raise SystemExit(1)
    access = str(token.json().get("access_token", ""))
    headers = {"authorization": f"Bearer {access}"}
    orgs = httpx.get(
        f"{keycloak}/admin/realms/agentic-runtime/organizations",
        headers=headers,
        timeout=20,
    )
    if orgs.status_code != 200 or not isinstance(orgs.json(), list):
        print(f"keycloak organizations {orgs.status_code}", file=sys.stderr)
        raise SystemExit(1)
    org_id = ""
    for org in orgs.json():
        if isinstance(org, dict) and org.get("alias") == "dev":
            org_id = str(org.get("id", ""))
    if not org_id:
        print("keycloak organisation dev was not imported", file=sys.stderr)
        raise SystemExit(1)
    for email in SEEDED:
        found = httpx.get(
            f"{keycloak}/admin/realms/agentic-runtime/users",
            params={"username": email, "exact": "true"},
            headers=headers,
            timeout=20,
        )
        rows = found.json() if found.status_code == 200 else []
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            print(f"keycloak user missing: {email}", file=sys.stderr)
            raise SystemExit(1)
        user_id = str(rows[0].get("id", ""))
        added = httpx.post(
            f"{keycloak}/admin/realms/agentic-runtime/organizations/{org_id}/members",
            headers={**headers, "content-type": "application/json"},
            content=f'"{user_id}"',
            timeout=20,
        )
        if added.status_code not in {201, 204, 409}:
            print(
                f"keycloak member {email} {added.status_code} {added.text[:200]}", file=sys.stderr
            )
            raise SystemExit(1)
        print(f"org member {email}")


def _keycloak_login(api: str, email: str) -> None:
    """Sign one seeded user in through the username step and then the password."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        page = client.get(f"{api}/api/v1/auth/login")
        for _ in range(6):
            body = page.text
            lowered = body.lower()
            if "https required" in lowered or "update account" in lowered:
                print(f"keycloak blocked the login page for {email}", file=sys.stderr)
                raise SystemExit(1)
            form = next(
                (item for item in parse_forms(body) if fill_login(item, email, PASSWORD)), None
            )
            if form is None:
                break
            payload = fill_login(form, email, PASSWORD)
            action = urljoin(str(page.url), str(form.get("action", "")))
            page = client.post(action, data=payload)
        final = str(page.url)
        if "error=" in final or "ar_session" not in client.cookies:
            print(f"keycloak login did not create a session for {email}: {final}", file=sys.stderr)
            raise SystemExit(1)
        print(f"keycloak login {email} landed on {final}")


def main() -> None:
    api_port = _port("AR_PORT", "8000")
    kc_port = _port("AR_KEYCLOAK_HOST_PORT", "8180")
    api = f"http://127.0.0.1:{api_port}"
    keycloak = f"http://127.0.0.1:{kc_port}"
    shifted = _env("AR_PG_HOST_PORT", "5432")
    if os.environ.get("FRESH_CLONE_EXPECT_SHIFTED") == "1" and shifted in {"", "5432"}:
        print("expected AUTO_PORTS to move Postgres off 5432", file=sys.stderr)
        raise SystemExit(1)
    _wait_ok(f"{api}/healthz")
    _dev_logins(api)
    _wait_ok(f"{keycloak}/realms/agentic-runtime")
    _ensure_org_members(keycloak)
    for email in SEEDED:
        _keycloak_login(api, email)


if __name__ == "__main__":
    main()
