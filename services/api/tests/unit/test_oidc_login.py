"""OIDC callback and the four dev users."""

import time
from pathlib import Path

import httpx
import orjson
import pytest
import respx
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from ar_api.auth.complete import LoginError, choose_organization, organization_aliases, profile_for
from ar_api.main import create_application
from ar_domain.secrets.crypto import parse_keyring

ISSUER = "http://localhost:8180/realms/agentic-runtime"
ROOT = Path(__file__).resolve().parents[4]


def _rsa_pem() -> bytes:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _id_token(pem: bytes, *, email: str, nonce: str, organization: object) -> str:
    now = int(time.time())
    encoded = jwt.encode(
        {"alg": "RS256"},
        {
            "iss": ISSUER,
            "aud": "account",
            "azp": "ar-web",
            "nonce": nonce,
            "exp": now + 600,
            "iat": now,
            "email": email,
            "organization": organization,
        },
        pem,
    )
    return encoded.decode() if isinstance(encoded, bytes) else str(encoded)


def _jwks(pem: bytes) -> dict[str, object]:
    private = serialization.load_pem_private_key(pem, password=None)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key = JsonWebKey.import_key(public.decode(), {"kty": "RSA", "use": "sig", "alg": "RS256"})
    exported = key.as_dict()
    exported["alg"] = "RS256"
    exported["use"] = "sig"
    return {"keys": [exported]}


def test_organization_claim_shapes() -> None:
    assert organization_aliases({"organization": {"dev": {}}}) == ["dev"]
    assert organization_aliases({"organization": {"8f1c": {"alias": "dev"}}}) == ["dev"]
    assert organization_aliases({"organization": ["dev", "other"]}) == ["dev", "other"]
    assert choose_organization(["dev", "other"], hint=None, email="a@dev.local") is None
    assert choose_organization(["dev", "other"], hint="dev", email="a@dev.local") == "dev"
    assert choose_organization(["other"], hint=None, email="a@dev.local") == "other"
    with pytest.raises(LoginError) as caught:
        profile_for("a@dev.local", "other")
    assert caught.value.code == "tenant_not_found"


def test_callback_signs_in_a_seeded_user() -> None:
    pem = _rsa_pem()
    token = _id_token(pem, email="approver@dev.local", nonce="n1", organization={"dev": {}})
    app = create_application()
    app.state.login_states["state1"] = {
        "verifier": "verifier",
        "nonce": "n1",
        "return_to": "/chat",
        "tenant": None,
    }
    with respx.mock:
        respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
            return_value=httpx.Response(
                200,
                json={"id_token": token, "access_token": "at", "refresh_token": "rt"},
            )
        )
        respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
            return_value=httpx.Response(200, json=_jwks(pem))
        )
        client = TestClient(app)
        callback = client.get("/api/v1/auth/callback?code=abc&state=state1", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/chat"
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["user"]["email"] == "approver@dev.local"
    assert body["user"]["displayName"] == "Dev Approver"
    assert "approvals:decide" in body["permissions"]
    assert "tenant:manage" not in body["permissions"]
    actions = [item["action"] for item in app.state.audit_api.events]
    assert "auth.login" in actions


def test_callback_asks_for_a_tenant_when_several_match() -> None:
    pem = _rsa_pem()
    token = _id_token(
        pem,
        email="admin@dev.local",
        nonce="n2",
        organization={"dev": {}, "other": {}},
    )
    app = create_application()
    app.state.login_states["state2"] = {
        "verifier": "verifier",
        "nonce": "n2",
        "return_to": "/chat",
        "tenant": None,
    }
    with respx.mock:
        respx.post(f"{ISSUER}/protocol/openid-connect/token").mock(
            return_value=httpx.Response(200, json={"id_token": token, "access_token": "at"})
        )
        respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
            return_value=httpx.Response(200, json=_jwks(pem))
        )
        client = TestClient(app)
        callback = client.get("/api/v1/auth/callback?code=abc&state=state2", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/select-tenant"


def test_dev_login_accepts_each_seeded_user() -> None:
    client = TestClient(create_application())
    for email, permission in (
        ("admin@dev.local", "tenant:manage"),
        ("builder@dev.local", "agents:create"),
        ("member@dev.local", "chat:use"),
        ("approver@dev.local", "approvals:decide"),
    ):
        client.cookies.clear()
        login = client.post(
            "/api/v1/auth/dev-login",
            json={"email": email},
            follow_redirects=False,
        )
        assert login.status_code == 303
        session = client.get("/api/v1/auth/session")
        assert session.json()["user"]["email"] == email
        assert permission in session.json()["permissions"]
    client.cookies.clear()
    unknown = client.post(
        "/api/v1/auth/dev-login",
        json={"email": "stranger@dev.local"},
        follow_redirects=False,
    )
    assert unknown.headers["location"] == "/login?error=unknown_user"


def test_realm_allows_local_http_and_names_users() -> None:
    realm = orjson.loads(
        (ROOT / "deploy/compose/keycloak/agentic-runtime-realm.json").read_text(encoding="utf-8")
    )
    assert realm["sslRequired"] == "none"
    assert realm["organizationsEnabled"] is True
    assert realm["loginTheme"] == "agentic"
    names = {user["username"]: (user["firstName"], user["lastName"]) for user in realm["users"]}
    assert names["admin@dev.local"] == ("Dev", "Admin")
    assert names["builder@dev.local"][1] == "Builder"
    assert names["member@dev.local"][1] == "Member"
    assert names["approver@dev.local"][1] == "Approver"
    assert realm["organizations"][0]["alias"] == "dev"
    web = next(client for client in realm["clients"] if client["clientId"] == "ar-web")
    claims = {mapper["config"]["claim.name"] for mapper in web["protocolMappers"]}
    assert {"email", "preferred_username", "organization"} <= claims


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
