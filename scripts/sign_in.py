"""Sign in with a userid and password, the way a person does.

The product signs people in itself (no external identity provider). The smoke and proof
scripts use this to get a real session for a seeded person.

    cookies = sign_in("http://localhost:3000", "admin@dev.local")
    client.cookies.update(cookies)

The password comes from ``AR_SIGN_IN_PASSWORD``; for the local dev tenant it defaults to the
dev password.
"""

from __future__ import annotations

import os

import httpx

# The local dev tenant's shared password (scripts/seed and ar_domain.identity.seed set it).
_DEV_PASSWORD = "dev-password"  # noqa: S105


class SignInError(RuntimeError):
    """The sign-in did not end in a session."""


def password_for(email: str) -> str:
    """The password for a seeded person: ``AR_SIGN_IN_PASSWORD``, else the dev password."""
    del email
    return os.environ.get("AR_SIGN_IN_PASSWORD", "").strip() or _DEV_PASSWORD


def sign_in(base_url: str, email: str, password: str | None = None) -> dict[str, str]:
    """Return the session cookies for a userid/password sign-in, or raise ``SignInError``."""
    secret = password or password_for(email)
    with httpx.Client(base_url=base_url, timeout=30) as client:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": secret})
        if response.status_code != 200:
            raise SignInError(
                f"sign-in failed for {email}: {response.status_code} {response.text[:200]}"
            )
        cookies = {name: client.cookies.get(name, "") for name in ("ar_session", "ar_csrf")}
    if not cookies.get("ar_session"):
        raise SignInError(f"sign-in for {email} produced no session cookie")
    return cookies
