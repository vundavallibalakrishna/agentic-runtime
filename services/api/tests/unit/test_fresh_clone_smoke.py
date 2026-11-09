"""The userid/password sign-in helper the smoke and proof scripts share."""

import importlib.util
from pathlib import Path

import httpx
import pytest
import respx

ROOT = Path(__file__).resolve().parents[4]


def _module():
    path = ROOT / "scripts" / "sign_in.py"
    spec = importlib.util.spec_from_file_location("sign_in_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@respx.mock
def test_sign_in_posts_the_password_and_returns_the_session_cookies() -> None:
    mod = _module()
    route = respx.post("http://localhost:3000/api/v1/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True},
            headers=[
                ("set-cookie", "ar_session=sess-1; Path=/; HttpOnly"),
                ("set-cookie", "ar_csrf=csrf-1; Path=/"),
            ],
        )
    )
    cookies = mod.sign_in("http://localhost:3000", "admin@dev.local", "dev-password")
    assert cookies["ar_session"] == "sess-1"
    assert cookies["ar_csrf"] == "csrf-1"
    sent = route.calls.last.request
    assert b"admin@dev.local" in sent.content
    assert b"dev-password" in sent.content


@respx.mock
def test_sign_in_raises_when_the_password_is_refused() -> None:
    mod = _module()
    respx.post("http://localhost:3000/api/v1/auth/login").mock(
        return_value=httpx.Response(401, json={"error": "invalid_credentials"})
    )
    with pytest.raises(mod.SignInError, match="sign-in failed"):
        mod.sign_in("http://localhost:3000", "admin@dev.local", "wrong")


def test_the_password_defaults_to_dev_and_honours_the_environment(monkeypatch) -> None:
    mod = _module()
    monkeypatch.delenv("AR_SIGN_IN_PASSWORD", raising=False)
    assert mod.password_for("admin@dev.local") == "dev-password"
    monkeypatch.setenv("AR_SIGN_IN_PASSWORD", "given-for-this-run")
    assert mod.password_for("ada@acme.example") == "given-for-this-run"
