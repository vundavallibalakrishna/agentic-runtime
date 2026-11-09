"""Health and userid/password sign-in for a fresh local stack.

``make dev`` blocks on honcho, so CI runs the same steps and then this script. Sign-in is
in-app: each seeded user signs in with their password (no external identity provider).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sign_in import SignInError, sign_in

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


def _password_login(api: str, email: str) -> None:
    """Sign one seeded user in with their password and confirm a session."""
    try:
        sign_in(api, email)
    except SignInError as exc:
        print(f"sign-in did not create a session: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"login {email}")


def main() -> None:
    api_port = _port("AR_PORT", "8000")
    api = f"http://127.0.0.1:{api_port}"
    shifted = _env("AR_PG_HOST_PORT", "5432")
    if os.environ.get("FRESH_CLONE_EXPECT_SHIFTED") == "1" and shifted in {"", "5432"}:
        print("expected AUTO_PORTS to move Postgres off 5432", file=sys.stderr)
        raise SystemExit(1)
    _wait_ok(f"{api}/healthz")
    for email in SEEDED:
        _password_login(api, email)


if __name__ == "__main__":
    main()
