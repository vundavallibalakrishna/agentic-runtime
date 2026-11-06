"""Health and Keycloak sign-in for a fresh local stack.

``make dev`` blocks on honcho, so CI runs the same steps and then this script.
Keycloak with organizations asks for the username and then the password.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sign_in import (
    SignInError,
    sign_in,
)

ROOT = Path(__file__).resolve().parents[1]
SEEDED = (
    "admin@dev.local",
    "builder@dev.local",
    "member@dev.local",
    "approver@dev.local",
)


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
    try:
        sign_in(api, email)
    except SignInError as exc:
        print(f"keycloak login did not create a session: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"keycloak login {email}")


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
    _wait_ok(f"{keycloak}/realms/agentic-runtime")
    _ensure_org_members(keycloak)
    for email in SEEDED:
        _keycloak_login(api, email)


if __name__ == "__main__":
    main()
