"""Userid/password sign-in at POST /api/v1/auth/login, and the dev-key bootstrap.

Task: M43. Sign-in is the product's own password check — no external identity provider.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ar_domain.secrets.crypto import parse_keyring
from ar_testing.demo import demo_application

ROOT = Path(__file__).resolve().parents[4]


def test_password_login_signs_in_a_seeded_user() -> None:
    client = TestClient(demo_application(), follow_redirects=False)
    answer = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert answer.status_code == 200
    assert "ar_session" in answer.cookies
    assert "ar_csrf" in answer.cookies
    # The issued session resolves to the person and their rows.
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["user"]["email"] == "admin@dev.local"
    assert "tenant:manage" in body["permissions"]


@pytest.mark.parametrize("password", ["wrong-password", ""])
def test_a_wrong_or_empty_password_is_refused(password: str) -> None:
    client = TestClient(demo_application(), follow_redirects=False)
    answer = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": password}
    )
    assert answer.status_code == 401
    assert "ar_session" not in answer.cookies


def test_an_unknown_person_is_refused_without_revealing_it() -> None:
    client = TestClient(demo_application(), follow_redirects=False)
    answer = client.post(
        "/api/v1/auth/login", json={"email": "nobody@dev.local", "password": "dev-password"}
    )
    assert answer.status_code == 401
    # Same error as a wrong password, so an address cannot be probed.
    assert answer.json()["error"] == "invalid_credentials"


def test_the_product_has_no_side_door_for_signing_in() -> None:
    """Task: M43. One in-app door and no bypass: the old dev-login is gone, an unauthenticated
    caller gets nothing, and the single login route takes a password (POST), not an IdP redirect."""
    client = TestClient(demo_application(), follow_redirects=False)
    for method in ("post", "get"):
        answer = getattr(client, method)(
            "/api/v1/auth/dev-login", params={"email": "admin@dev.local"}
        )
        assert answer.status_code in {401, 404, 405}
        assert "set-cookie" not in answer.headers
    assert client.get("/api/v1/auth/session").status_code == 401
    paths = demo_application().openapi()["paths"]
    assert not [path for path in paths if "dev-login" in path]
    assert "get" not in paths.get("/api/v1/auth/login", {})
    assert "post" in paths.get("/api/v1/auth/login", {})


def test_bootstrap_keyring_decodes_as_standard_base64() -> None:
    import importlib.util

    path = ROOT / "scripts" / "dev_keys.py"
    spec = importlib.util.spec_from_file_location("dev_keys", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = module.encryption_keyring().strip("'")
    ring = parse_keyring(raw)
    assert len(ring["k1"]) == 32
    import base64

    assert len(base64.b64decode(module.session_key())) == 32
    pem = "-----BEGIN PRIVATE KEY-----\\nABC\\n-----END PRIVATE KEY-----\\n"
    assert module.shell_value(pem) == f"'{pem}'"
