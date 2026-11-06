"""Sign in through the identity provider, the way a person does.

The product has one way in: the OIDC sign-in. The smoke and proof scripts use this to get
a real session for a person who exists in the identity provider and in the tenant.

    cookies = sign_in("http://localhost:3000", "admin@dev.local")
    client.cookies.update(cookies)

The password comes from ``AR_SIGN_IN_PASSWORD``. For a person of the local dev realm it
may be left unset: it is then read from the realm export that created that person.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from http.cookiejar import DefaultCookiePolicy
from pathlib import Path
from urllib.parse import urljoin

import httpx
import orjson

ROOT = Path(__file__).resolve().parents[1]
REALM_EXPORT = ROOT / "deploy" / "compose" / "keycloak" / "agentic-runtime-realm.json"


class SignInError(RuntimeError):
    """The sign-in did not end in a session."""


def allow_secure_cookies_on_localhost() -> None:
    """Send Keycloak's Secure cookies back to plain HTTP on localhost.

    Keycloak 26 treats localhost as a secure context, so ``AUTH_SESSION_ID``
    is marked Secure even when the dev realm is served over HTTP. Browsers
    return that cookie to localhost. The default cookie policy does not, and
    the login post then has no session.
    """
    if getattr(allow_secure_cookies_on_localhost, "done", False):
        return
    original = DefaultCookiePolicy.return_ok_secure

    def return_ok_secure(self: DefaultCookiePolicy, cookie: object, request: object) -> bool:
        host = str(getattr(request, "host", "")).rsplit(":", 1)[0]
        secure = bool(getattr(cookie, "secure", False))
        if secure and host in {"localhost", "127.0.0.1"}:
            return True
        return bool(original(self, cookie, request))

    DefaultCookiePolicy.return_ok_secure = return_ok_secure  # type: ignore[method-assign]
    allow_secure_cookies_on_localhost.done = True  # type: ignore[attr-defined]


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


def password_for(email: str) -> str:
    """The password to type for this person."""
    given = os.environ.get("AR_SIGN_IN_PASSWORD", "")
    if given:
        return given
    realm = orjson.loads(REALM_EXPORT.read_bytes())
    for user in realm.get("users", []):
        if str(user.get("email", "")).lower() == email.lower():
            for credential in user.get("credentials", []):
                if credential.get("type") == "password" and credential.get("value"):
                    return str(credential["value"])
    raise SignInError(f"set AR_SIGN_IN_PASSWORD: {email} is not in the local dev realm export")


def page_hint(html: str) -> str:
    """The visible text of a page, shortened, for an error message."""
    flags = re.IGNORECASE | re.DOTALL
    without_script = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=flags)
    without_style = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_script, flags=flags)
    text = re.sub(r"<[^>]+>", " ", without_style)
    return re.sub(r"\s+", " ", text).strip()[:240]


def sign_in(base_url: str, email: str, password: str | None = None) -> dict[str, str]:
    """Walk the sign-in pages (username, then password) and return the session cookies."""
    allow_secure_cookies_on_localhost()
    secret = password_for(email) if password is None else password
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        page = client.get(f"{base_url.rstrip('/')}/api/v1/auth/login")
        for _ in range(6):
            body = page.text
            lowered = body.lower()
            if "https required" in lowered or "update account" in lowered:
                raise SignInError(f"the identity provider blocked the sign-in page for {email}")
            form = next(
                (item for item in parse_forms(body) if fill_login(item, email, secret)), None
            )
            if form is None:
                break
            payload = fill_login(form, email, secret)
            action = urljoin(str(page.url), str(form.get("action", "")))
            page = client.post(action, data=payload)
        final = str(page.url)
        if "error=" in final or "ar_session" not in client.cookies:
            raise SignInError(
                f"no session for {email}: {page.status_code} {final} {page_hint(page.text)}"
            )
        return {name: value for name, value in client.cookies.items() if name.startswith("ar_")}
