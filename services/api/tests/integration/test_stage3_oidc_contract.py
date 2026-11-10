"""OIDC against a local mock IdP container. Proof label: contract.

Real HTTP. The model is not called. The container generates its signing key
and receives a client secret minted in this test. No IdP secret is stored in
the repository.
"""

import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from testcontainers.core.container import DockerContainer

from ar_testing.demo import demo_application

_SCRIPT = Path(__file__).with_name("mock_oidc_idp.py")
pytestmark = pytest.mark.integration


def test_oidc_auth_code_and_bearer_against_a_mock_idp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proof label: contract."""
    secret = secrets.token_urlsafe(24)
    container = DockerContainer("python:3.12-slim")
    container.with_exposed_ports(8080)
    container.with_volume_mapping(str(_SCRIPT), "/mock_oidc_idp.py", mode="ro")
    container.with_env("OIDC_CLIENT_ID", "ar-api")
    container.with_env("OIDC_CLIENT_SECRET", secret)
    container.with_env("OIDC_EMAIL", "admin@dev.local")
    container.with_command(
        "bash -lc 'pip install -q \"pyjwt[crypto]==2.15.1\" && python /mock_oidc_idp.py'"
    )
    container.start()
    try:
        port = container.get_exposed_port(8080)
        issuer = f"http://127.0.0.1:{port}"
        deadline = __import__("time").time() + 60
        discovered = False
        while __import__("time").time() < deadline:
            try:
                answer = httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=1.0)
                if answer.status_code == 200 and answer.json().get("issuer") == issuer:
                    discovered = True
                    break
            except httpx.HTTPError:
                __import__("time").sleep(0.5)
        assert discovered, "mock IdP did not publish discovery"
        monkeypatch.setenv("AR_ENV", "ci")
        monkeypatch.setenv("AR_AUTH_MODE", "oidc")
        monkeypatch.setenv("AR_OIDC_ISSUER", issuer)
        monkeypatch.setenv("AR_OIDC_CLIENT_ID", "ar-api")
        monkeypatch.setenv("AR_OIDC_CLIENT_SECRET", secret)
        monkeypatch.setenv("AR_OIDC_AUDIENCE", "ar-api")
        monkeypatch.setenv("AR_OIDC_REQUIRE_MFA", "true")
        monkeypatch.setenv("AR_PUBLIC_URL", "http://localhost:3000")
        client = TestClient(demo_application(), follow_redirects=False)
        started = client.get("/api/v1/auth/oidc/start")
        assert started.status_code == 302
        authorized = httpx.get(started.headers["location"], follow_redirects=False, timeout=5.0)
        assert authorized.status_code == 302
        query = parse_qs(urlparse(authorized.headers["location"]).query)
        callback = client.get(
            "/api/v1/auth/callback",
            params={"code": query["code"][0], "state": query["state"][0]},
        )
        assert callback.status_code == 302, callback.text
        assert "ar_session" in callback.cookies
        session = client.get("/api/v1/auth/session")
        assert session.status_code == 200
        assert session.json()["user"]["email"] == "admin@dev.local"
        token = httpx.get(f"{issuer}/access-token", timeout=5.0).json()["access_token"]
        anonymous = TestClient(client.app, follow_redirects=False)
        bearer = anonymous.get(
            "/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        assert bearer.status_code == 200
        assert bearer.json()["user"]["email"] == "admin@dev.local"
        weak = httpx.get(f"{issuer}/access-token?mfa=0", timeout=5.0).json()["access_token"]
        refused = anonymous.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {weak}"}
        )
        assert refused.status_code == 401
    finally:
        container.stop()
