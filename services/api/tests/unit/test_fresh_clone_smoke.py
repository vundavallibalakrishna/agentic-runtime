"""The fresh-clone login parser, without a running Keycloak."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _forms():
    path = ROOT / "scripts" / "fresh_clone_smoke.py"
    spec = importlib.util.spec_from_file_location("fresh_clone_smoke", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_username_step_then_password_step() -> None:
    forms = _forms()
    username = forms.parse_forms('<form action="/step1"><input name="username"></form>')[0]
    assert forms.fill_login(username, "admin@dev.local", "dev-password") == {
        "username": "admin@dev.local"
    }
    password = forms.parse_forms(
        '<form action="/step2"><input name="username" value="admin@dev.local">'
        '<input name="password" type="password"></form>'
    )[0]
    filled = forms.fill_login(password, "admin@dev.local", "dev-password")
    assert filled is not None
    assert filled["username"] == "admin@dev.local"
    assert filled["password"] == "dev-password"  # noqa: S105


def test_single_page_login_fills_both_fields() -> None:
    forms = _forms()
    page = forms.parse_forms(
        '<form action="/auth"><input name="username"><input name="password"></form>'
    )[0]
    filled = forms.fill_login(page, "builder@dev.local", "dev-password")
    assert filled == {"username": "builder@dev.local", "password": "dev-password"}
