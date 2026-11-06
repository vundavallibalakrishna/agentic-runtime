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

from ar_api.auth.complete import LoginError, choose_organization, organization_aliases
from ar_domain.secrets.crypto import parse_keyring
from ar_testing.demo import demo_application

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
    assert choose_organization(["dev", "other"], hint=None) is None
    assert choose_organization(["dev", "other"], hint="dev") == "dev"
    assert choose_organization(["other"], hint=None) == "other"
    # A token that names no organization is left to the tenant the process serves.
    assert choose_organization([], hint=None) == ""
    with pytest.raises(LoginError) as caught:
        choose_organization(["other"], hint="dev")
    assert caught.value.code == "tenant_not_found"


def test_callback_signs_in_a_seeded_user() -> None:
    pem = _rsa_pem()
    token = _id_token(pem, email="approver@dev.local", nonce="n1", organization={"dev": {}})
    app = demo_application()
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
    app = demo_application()
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


def _callback_as(app: object, email: str, organization: str = "dev") -> TestClient:
    """Finish a sign-in whose token named this address and organization."""

    async def complete(code: str, saved: dict[str, object]) -> dict[str, object]:
        del code, saved
        return {"email": email, "organization": organization, "access_token": "at"}

    app.state.complete_login = complete  # type: ignore[attr-defined]
    app.state.login_states["s"] = {"return_to": "/chat"}  # type: ignore[attr-defined]
    client = TestClient(app, follow_redirects=False)  # type: ignore[arg-type]
    client.landed = client.get("/api/v1/auth/callback?code=c&state=s")  # type: ignore[attr-defined]
    return client


def test_each_person_of_the_tenant_signs_in_with_their_own_permissions() -> None:
    for email, permission in (
        ("admin@dev.local", "tenant:manage"),
        ("builder@dev.local", "agents:create"),
        ("member@dev.local", "chat:use"),
        ("approver@dev.local", "approvals:decide"),
    ):
        client = _callback_as(demo_application(), email)
        assert client.landed.headers["location"] == "/chat"  # type: ignore[attr-defined]
        session = client.get("/api/v1/auth/session").json()
        assert session["user"]["email"] == email
        assert permission in session["permissions"]
        assert session["tenant"]["slug"] == "dev"


@pytest.mark.parametrize(
    ("email", "organization"),
    [("stranger@dev.local", "dev"), ("admin@dev.local", "other"), ("ada@acme.example", "")],
)
def test_someone_who_is_not_a_person_of_the_tenant_served_is_refused(
    email: str, organization: str
) -> None:
    client = _callback_as(demo_application(), email, organization)
    assert client.landed.headers["location"] == "/login?error=tenant_not_found"  # type: ignore[attr-defined]
    assert client.get("/api/v1/auth/session").status_code == 401


def test_the_product_has_no_side_door_for_signing_in() -> None:
    """Task: M38b-T05b. The identity provider is the only way in."""
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
    assert all("offline_access" in user["realmRoles"] for user in realm["users"])
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


@pytest.mark.parametrize(
    "failure",
    [
        "exchange",
        "invalid_json",
        "missing_token",
        "certs",
        "bad_jwks",
        "nonce",
        "email",
        "organization",
        "network",
    ],
)
def test_callback_rejects_invalid_exchange_without_issuing_a_session(failure: str) -> None:
    pem = _rsa_pem()
    token = _id_token(
        pem,
        email="missing" if failure == "email" else "admin@dev.local",
        nonce="wrong" if failure == "nonce" else "n1",
        organization={"other" if failure == "organization" else "dev": {}},
    )
    app = demo_application()
    app.state.login_states["invalid"] = {
        "verifier": "verifier",
        "nonce": "n1",
        "return_to": "/chat",
        "tenant": None,
    }
    with respx.mock:
        exchange = respx.post(f"{ISSUER}/protocol/openid-connect/token")
        if failure == "network":
            exchange.mock(side_effect=httpx.ConnectError("unavailable"))
        elif failure == "exchange":
            exchange.mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
        elif failure == "invalid_json":
            exchange.mock(return_value=httpx.Response(400, text="Unavailable"))
        else:
            exchange.mock(
                return_value=httpx.Response(
                    200, json={} if failure == "missing_token" else {"id_token": token}
                )
            )
        if failure not in {"network", "exchange", "invalid_json", "missing_token"}:
            respx.get(f"{ISSUER}/protocol/openid-connect/certs").mock(
                return_value=httpx.Response(
                    503 if failure == "certs" else 200,
                    json=[] if failure == "bad_jwks" else _jwks(pem),
                )
            )
        client = TestClient(app)
        result = client.get("/api/v1/auth/callback?code=bad&state=invalid", follow_redirects=False)
    assert result.status_code == 302
    assert result.headers["location"].startswith("/login?error=")
    assert "ar_session" not in client.cookies
    assert app.state.login_states == {}
