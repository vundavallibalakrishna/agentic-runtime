"""Stage 3 identity. Proof label: unit.

OIDC token checks, cookie flags, shared lockout, and login problem responses
run in process. No network and no model.
"""

import base64
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_api.auth.complete import LoginError
from ar_api.auth.lockout import ValkeyLoginLockout, lockout_subject
from ar_api.auth.mode import assert_auth_mode, cookies_are_secure, resolve_auth_mode
from ar_api.auth.oidc import claims_have_mfa
from ar_api.main import Settings
from ar_common.errors import RateLimitedError
from ar_common.settings import DeploymentMode, EnvName
from ar_common.time import utcnow
from ar_common.web.problems import problem_response
from ar_domain.identity.guests import _totp
from ar_testing.demo import demo_application

_SECRET = SecretStr("staging-cursor-secret-value")


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"_env_file": None, "cursor_secret": _SECRET}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_password_mode_is_not_the_production_default() -> None:
    """Proof label: unit."""
    prod = _settings(env=EnvName.PROD, auth_mode="password", deployment_mode=DeploymentMode.SAAS)
    with pytest.raises(RuntimeError, match="not the production default"):
        assert_auth_mode(prod)
    implied = _settings(env=EnvName.PROD, auth_mode="")
    assert resolve_auth_mode(implied) is resolve_auth_mode(
        _settings(env=EnvName.PROD, auth_mode="oidc")
    )
    with pytest.raises(RuntimeError, match="AR_OIDC_ISSUER"):
        assert_auth_mode(implied)
    single = _settings(
        env=EnvName.PROD,
        auth_mode="password",
        deployment_mode=DeploymentMode.SINGLE_TENANT,
        password_login=True,
    )
    assert_auth_mode(single)
    dev = _settings(env=EnvName.DEV, auth_mode="")
    assert resolve_auth_mode(dev).value == "password"
    assert_auth_mode(dev)


def test_helm_default_is_oidc() -> None:
    """Proof label: unit."""
    text = Path("deploy/helm/agentic-runtime/values.yaml").read_text()
    assert "AR_AUTH_MODE: oidc" in text
    assert "AR_PASSWORD_LOGIN: 'false'" in text
    dev = Path("deploy/helm/agentic-runtime/values-dev.yaml").read_text()
    assert "AR_AUTH_MODE: password" in dev


def test_cookies_are_secure_httponly_outside_dev() -> None:
    """Proof label: unit."""
    from starlette.responses import JSONResponse

    from ar_api.auth.cookies import write_session_cookies

    settings = _settings(env=EnvName.STAGING)
    assert cookies_are_secure(settings)
    response = JSONResponse({"ok": True})
    write_session_cookies(response, settings, "sid", "csrf")
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie or "SameSite=Lax" in cookie


def test_dev_cookies_stay_usable_without_secure() -> None:
    """Proof label: unit."""
    client = TestClient(demo_application(), follow_redirects=False)
    answer = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert answer.status_code == 200
    assert "Secure" not in answer.headers["set-cookie"]
    assert answer.headers["content-type"].startswith("application/json")


def test_login_failures_are_problem_json_and_lock_together() -> None:
    """Proof label: unit. Two lockout stores share one Valkey stand-in."""

    class Shared:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.expires: dict[str, int] = {}

        async def incr(self, key: str) -> int:
            count = int(self.values.get(key, "0")) + 1
            self.values[key] = str(count)
            return count

        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            self.values[key] = value
            if ex:
                self.expires[key] = ex

        async def delete(self, *keys: str) -> None:
            for key in keys:
                self.values.pop(key, None)
                self.expires.pop(key, None)

        async def ttl(self, key: str) -> int:
            if key not in self.values:
                return -2
            return self.expires.get(key, -1)

    redis = Shared()
    first = ValkeyLoginLockout("redis://unused", client=redis, max_attempts=2, lockout_s=30)
    second = ValkeyLoginLockout("redis://unused", client=redis, max_attempts=2, lockout_s=30)
    subject = lockout_subject("ada@example.com")

    async def _run() -> None:
        assert await first.record_failure(subject) == 0
        retry = await first.record_failure(subject)
        assert retry == 30
        assert await second.retry_after(subject) == 30

    import asyncio

    asyncio.run(_run())  # the test is not marked asyncio; run the coroutine once
    client = TestClient(demo_application(), follow_redirects=False)
    client.app.state.login_lockout = first  # type: ignore[attr-defined]
    blocked = client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope"}
    )
    assert blocked.status_code == 429
    assert blocked.headers["content-type"].startswith("application/problem+json")
    assert blocked.json()["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) == 30


def test_rate_limited_problem_carries_retry_after() -> None:
    """Proof label: unit."""
    response = problem_response(
        RateLimitedError("too many attempts", retry_after=12),
        instance="/api/v1/auth/login",
        request_id="req",
    )
    assert response.headers["retry-after"] == "12"
    assert response.media_type == "application/problem+json"


def test_local_totp_is_required_when_the_user_has_a_secret() -> None:
    """Proof label: unit."""
    app = demo_application()
    client = TestClient(app, follow_redirects=False)
    secret = b"12345678901234567890"
    identity = app.state.identity_provider  # type: ignore[attr-defined]
    from ar_domain.db.context import Principal, TenantContext
    from ar_testing.demo_people import DEV_TENANT_ID

    ctx = TenantContext.from_principal(
        Principal(kind="system", id="test", tenant_id=DEV_TENANT_ID), "mfa"
    )
    user = None

    async def _enroll() -> None:
        nonlocal user
        store = identity(ctx)
        user = await store.get_user_by_email("admin@dev.local")
        user.attributes = {"totp_secret": base64.b64encode(secret).decode()}

    import asyncio

    asyncio.run(_enroll())
    code = _totp(secret, int(utcnow().timestamp()))
    refused = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert refused.status_code == 401
    assert refused.json()["detail"] == "mfa required"
    accepted = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@dev.local", "password": "dev-password", "otp": code},
    )
    assert accepted.status_code == 200


def test_idp_mfa_claim_and_browser_code_flow() -> None:
    """Proof label: unit. The IdP is an in-process stand-in, not a container."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public["kid"] = "unit"
    public["alg"] = "RS256"
    public["use"] = "sig"
    app = demo_application()
    settings = app.state.settings
    settings.auth_mode = "oidc"
    settings.oidc_issuer = "http://idp.test"
    settings.oidc_client_id = "ar-api"
    settings.oidc_client_secret = SecretStr("unit-client-secret")
    settings.oidc_audience = "ar-api"
    settings.oidc_require_mfa = True
    settings.public_url = "http://localhost:3000"
    app.state.oidc_jwks = {"keys": [public]}

    class Http:
        def __init__(self) -> None:
            self.nonce = ""

        async def get(self, url: str) -> object:
            assert url.endswith("/.well-known/openid-configuration")
            return _Json(
                {
                    "issuer": "http://idp.test",
                    "authorization_endpoint": "http://idp.test/authorize",
                    "token_endpoint": "http://idp.test/token",
                    "jwks_uri": "http://idp.test/jwks",
                }
            )

        async def post(self, url: str, data: dict[str, str] | None = None) -> object:
            del url, data
            token = jwt.encode(
                {
                    "iss": "http://idp.test",
                    "aud": "ar-api",
                    "sub": "admin@dev.local",
                    "email": "admin@dev.local",
                    "nonce": self.nonce,
                    "amr": ["mfa"],
                },
                private,
                algorithm="RS256",
                headers={"kid": "unit"},
            )
            return _Json({"id_token": token})

    http = Http()
    app.state.oidc_http = http
    assert claims_have_mfa({"amr": ["pwd"]}, settings) is False
    assert claims_have_mfa({"acr": "mfa"}, settings) is True
    client = TestClient(app, follow_redirects=False)
    started = client.get("/api/v1/auth/oidc/start")
    assert started.status_code == 302
    query = parse_qs(urlparse(started.headers["location"]).query)
    http.nonce = query["nonce"][0]
    assert query["code_challenge_method"] == ["S256"]
    callback = client.get(
        "/api/v1/auth/callback", params={"code": "one-time", "state": query["state"][0]}
    )
    assert callback.status_code == 302
    assert "ar_session" in callback.cookies
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["email"] == "admin@dev.local"
    weak = jwt.encode(
        {
            "iss": "http://idp.test",
            "aud": "ar-api",
            "sub": "admin@dev.local",
            "email": "admin@dev.local",
        },
        private,
        algorithm="RS256",
        headers={"kid": "unit"},
    )
    denied = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {weak}"})
    assert denied.status_code == 401
    strong = jwt.encode(
        {
            "iss": "http://idp.test",
            "aud": "ar-api",
            "sub": "admin@dev.local",
            "email": "admin@dev.local",
            "amr": ["otp"],
        },
        private,
        algorithm="RS256",
        headers={"kid": "unit"},
    )
    allowed = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {strong}"})
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_shared_lockout_and_oidc_state_fail_closed() -> None:
    """Proof label: unit."""
    from ar_api.auth.lockout import MemoryLoginLockout
    from ar_api.auth.oidc import MemoryOidcState, ValkeyOidcState
    from ar_common.errors import UnavailableError

    memory = MemoryLoginLockout(max_attempts=1, lockout_s=10)
    assert await memory.record_failure("ada") == 10
    assert await memory.retry_after("ada") > 0
    await memory.clear("ada")
    assert await memory.retry_after("ada") == 0

    class Broken:
        async def ttl(self, key: str) -> int:
            del key
            raise RuntimeError("down")

        async def incr(self, key: str) -> int:
            del key
            raise RuntimeError("down")

        async def delete(self, *keys: str) -> None:
            del keys
            raise RuntimeError("down")

    broken = ValkeyLoginLockout("redis://unused", client=Broken(), max_attempts=1, lockout_s=5)
    with pytest.raises(UnavailableError):
        await broken.retry_after("ada")
    with pytest.raises(UnavailableError):
        await broken.record_failure("ada")
    with pytest.raises(UnavailableError):
        await broken.clear("ada")

    states = MemoryOidcState()
    await states.put("s", {"verifier": "v"}, 10)
    assert (await states.pop("s")) == {"verifier": "v"}
    assert await states.pop("s") is None

    class Store:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            del ex
            self.values[key] = value

        async def get(self, key: str) -> str | None:
            return self.values.get(key)

        async def delete(self, key: str) -> None:
            self.values.pop(key, None)

    shared = Store()
    valkey_state = ValkeyOidcState("redis://unused", client=shared)
    await valkey_state.put("s", {"nonce": "n"}, 30)
    assert (await valkey_state.pop("s")) == {"nonce": "n"}
    assert await valkey_state.pop("missing") is None

    class Down:
        async def set(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            raise RuntimeError("down")

        async def get(self, key: str) -> None:
            del key
            raise RuntimeError("down")

    down = ValkeyOidcState("redis://unused", client=Down())
    with pytest.raises(LoginError):
        await down.put("s", {"nonce": "n"}, 30)
    with pytest.raises(LoginError):
        await down.pop("s")


def test_password_mode_hides_oidc_and_oidc_hides_password() -> None:
    """Proof label: unit."""
    client = TestClient(demo_application(), follow_redirects=False)
    assert client.get("/api/v1/auth/oidc/start").status_code == 404
    blank = client.post("/api/v1/auth/login", json={"email": "", "password": ""})
    assert blank.status_code == 401
    signed = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert signed.status_code == 200
    client.app.state.settings.auth_mode = "oidc"  # type: ignore[attr-defined]
    refused = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert refused.status_code == 403
    assert refused.headers["content-type"].startswith("application/problem+json")
    csrf = {"x-csrf-token": client.cookies.get("ar_csrf") or ""}
    step = client.post("/api/v1/auth/step-up", headers=csrf, json={"confirmed": True})
    assert step.status_code == 200
    assert step.json()["redirectUrl"].endswith("purpose=step-up")
    client.post("/api/v1/auth/logout", headers=csrf)
    missing = client.get("/api/v1/auth/callback", params={"code": "x", "state": "nope"})
    assert missing.status_code == 401


def test_a_bad_token_and_a_missing_issuer_do_not_sign_anyone_in() -> None:
    """Proof label: unit."""
    from ar_api.auth.oidc import OidcClient

    app = demo_application()
    settings = app.state.settings
    settings.oidc_issuer = "http://idp.test"
    settings.oidc_client_id = "ar-api"
    client = OidcClient(settings, app.state.oidc_states)
    assert client.verify("not-a-jwt", audience="ar-api") is None
    assert claims_have_mfa({"amr": "otp"}, settings) is True
    settings.oidc_issuer = ""
    denied = TestClient(app).get(
        "/api/v1/me",
        headers={"Authorization": "Bearer eyJhbGciOiJub25lIn0.e30.e30"},
    )
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_oidc_discovery_over_httpx_and_a_bad_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proof label: unit."""
    import httpx

    from ar_api.auth.oidc import MemoryOidcState, OidcClient, ValkeyOidcState

    settings = _settings(
        env=EnvName.DEV,
        oidc_issuer="http://idp.test",
        oidc_client_id="ar-api",
        oidc_redirect_url="http://localhost:3000/api/v1/auth/callback",
        oidc_require_mfa=False,
    )

    class Response:
        def __init__(self, payload: object, status: int = 200) -> None:
            self.payload = payload
            self.status_code = status

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "http://idp.test")
                raise httpx.HTTPStatusError("no", request=request, response=httpx.Response(500))

        def json(self) -> object:
            return self.payload

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str) -> Response:
            del url
            return Response(
                {
                    "issuer": "http://idp.test",
                    "authorization_endpoint": "http://idp.test/authorize",
                    "token_endpoint": "http://idp.test/token",
                    "jwks_uri": "http://idp.test/jwks",
                }
            )

        async def post(self, url: str, data: dict[str, str] | None = None) -> Response:
            del url, data
            return Response(["nope"])

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: Client())
    oidc = OidcClient(settings, MemoryOidcState())
    assert oidc.redirect_uri().endswith("/callback")
    document = await oidc.discovery()
    assert document["jwks_uri"].endswith("/jwks")
    with pytest.raises(LoginError):
        await oidc._post_form("http://idp.test/token", {"code": "x"})
    started = await oidc.authorization_url(purpose="login", next_path="//evil.example")
    assert "code_challenge=" in started
    token = jwt.encode(
        {"iss": "http://idp.test", "aud": "ar-api"},
        "unit-test-hmac-secret-value-32b",
        algorithm="HS256",
    )
    oidc.jwks = {"keys": []}
    assert oidc.verify(token, audience="ar-api") is None
    oidc.jwks = {"keys": "no"}
    assert oidc.verify(token, audience="ar-api") is None
    oidc.jwks = None
    oidc.jwks_uri = "http://127.0.0.1:1/jwks"
    assert oidc.verify(token, audience="ar-api") is None

    class BrokenClient(Client):
        async def get(self, url: str) -> Response:
            del url
            raise RuntimeError("down")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: BrokenClient())
    down = OidcClient(settings, MemoryOidcState())
    with pytest.raises(LoginError):
        await down.discovery()

    class Raw:
        async def get(self, key: str) -> bytes:
            del key
            return b"not-json"

        async def delete(self, key: str) -> None:
            del key

    assert await ValkeyOidcState("redis://unused", client=Raw()).pop("s") is None
    offline = ValkeyOidcState("redis://127.0.0.1:1")
    with pytest.raises(LoginError):
        await offline.put("s", {"nonce": "n"}, 1)


@pytest.mark.asyncio
async def test_oidc_refuses_a_bad_discovery_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proof label: unit."""
    import httpx

    from ar_api.auth.oidc import MemoryOidcState, OidcClient, ValkeyOidcState

    settings = _settings(
        env=EnvName.DEV,
        oidc_issuer="http://idp.test",
        oidc_client_id="ar-api",
        oidc_require_mfa=False,
    )
    assert claims_have_mfa({}, settings) is True

    class Response:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return self.payload

    class Client:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str) -> Response:
            del url
            if isinstance(self.payload, BaseException):
                raise self.payload
            return Response(self.payload)

        async def post(self, url: str, data: dict[str, str] | None = None) -> Response:
            del url, data
            return Response({})

    payloads: dict[str, object] = {"current": {"issuer": "http://idp.test"}}

    def factory(*args: object, **kwargs: object) -> Client:
        del args, kwargs
        return Client(payloads["current"])

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    oidc = OidcClient(settings, MemoryOidcState())
    with pytest.raises(LoginError):
        await oidc.authorization_url(purpose="login", next_path="/")
    payloads["current"] = {"issuer": "http://other.example"}
    with pytest.raises(LoginError):
        await OidcClient(settings, MemoryOidcState()).discovery()
    payloads["current"] = LoginError("oidc_unavailable")
    with pytest.raises(LoginError):
        await OidcClient(settings, MemoryOidcState()).discovery()
    settings.oidc_issuer = ""
    with pytest.raises(LoginError):
        await OidcClient(settings, MemoryOidcState()).discovery()
    settings.oidc_issuer = "http://idp.test"
    bare = OidcClient(settings, MemoryOidcState())
    bare.jwks = None
    bare.jwks_uri = ""
    assert bare.verify("a.b.c", audience="ar-api") is None

    class ListStore:
        async def get(self, key: str) -> str:
            del key
            return "[1]"

        async def delete(self, key: str) -> None:
            del key

    assert await ValkeyOidcState("redis://unused", client=ListStore()).pop("s") is None


def test_login_lockout_and_step_up_failure_paths() -> None:
    """Proof label: unit."""
    from ar_common.errors import UnavailableError

    client = TestClient(demo_application(), follow_redirects=False)

    class Down:
        async def retry_after(self, subject: str) -> int:
            del subject
            raise UnavailableError("down")

    client.app.state.login_lockout = Down()  # type: ignore[attr-defined]
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "nope"}
        ).status_code
        == 503
    )

    class FailCount:
        async def retry_after(self, subject: str) -> int:
            del subject
            return 0

        async def record_failure(self, subject: str) -> int:
            del subject
            raise UnavailableError("down")

    client.app.state.login_lockout = FailCount()  # type: ignore[attr-defined]
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "nope"}
        ).status_code
        == 503
    )

    class Locked:
        async def retry_after(self, subject: str) -> int:
            del subject
            return 7

    client.app.state.login_lockout = Locked()  # type: ignore[attr-defined]
    locked = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "nope"}
    )
    assert locked.status_code == 429
    assert locked.headers["retry-after"] == "7"

    class ClearDown:
        async def retry_after(self, subject: str) -> int:
            del subject
            return 0

        async def record_failure(self, subject: str) -> int:
            del subject
            return 0

        async def clear(self, subject: str) -> None:
            del subject
            raise UnavailableError("down")

    client.app.state.login_lockout = ClearDown()  # type: ignore[attr-defined]
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@dev.local", "password": "dev-password"},
        ).status_code
        == 503
    )


def test_step_up_password_factor_and_jwks_shape() -> None:
    """Proof label: unit."""
    client = TestClient(demo_application(), follow_redirects=False)
    signed = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert signed.status_code == 200
    csrf = {"x-csrf-token": client.cookies.get("ar_csrf") or ""}
    quiet = client.post("/api/v1/auth/step-up", headers=csrf, json={})
    assert quiet.json()["steppedUp"] == "false"
    client.app.state.settings.password_mfa = True  # type: ignore[attr-defined]
    blocked = client.post(
        "/api/v1/auth/step-up", headers=csrf, json={"confirmed": True, "otp": "000000"}
    )
    assert blocked.status_code == 401
    client.app.state.settings.password_mfa = False  # type: ignore[attr-defined]
    client.app.state.settings.internal_jwt_jwks = "[]"  # type: ignore[attr-defined]
    assert client.get("/api/v1/.well-known/jwks.json").json() == {"keys": []}
    client.app.state.settings.internal_jwt_jwks = '{"keys":[{"kid":"k"}]}'  # type: ignore[attr-defined]
    assert client.get("/api/v1/.well-known/jwks.json").json()["keys"][0]["kid"] == "k"


class _Json:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload
