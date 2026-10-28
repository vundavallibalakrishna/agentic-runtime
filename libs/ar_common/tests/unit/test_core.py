"""Unit tests for ar_common."""

import asyncio
import hashlib
import inspect
import runpy
import uuid
from datetime import timedelta
from typing import Any, get_type_hints

import httpx
import pytest
import time_machine
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from ar_common import keys as keymod
from ar_common import serve
from ar_common.errors import (
    ArError,
    ErrorCode,
    FieldError,
    NotFoundError,
    PayloadTooLargeError,
    http_status_for,
)
from ar_common.http import assert_public_url, http_client, is_public_ip
from ar_common.ids import new_id
from ar_common.internal_auth import ALLOWED_CALLERS
from ar_common.internal_jwt import (
    MemoryJtiCache,
    generate_keypair,
    sign_internal_jwt,
    verify_internal_jwt,
)
from ar_common.jcs import args_hash, canonical_json
from ar_common.logging import _scrub, setup_logging
from ar_common.mode import is_saas, is_single_tenant
from ar_common.pagination import decode_cursor, encode_cursor
from ar_common.s3 import S3Store
from ar_common.settings import (
    BaseServiceSettings,
    DeploymentMode,
    EnvName,
    get_settings,
    set_settings,
)
from ar_common.time import utcnow
from ar_common.valkey import valkey_client
from ar_common.web import create_app

# The public catalogue from api-conventions §5, in table order.
_CATALOGUE = {
    "bad_request": 400,
    "invalid_cursor": 400,
    "unauthenticated": 401,
    "forbidden": 403,
    "csrf_failed": 403,
    "tenant_suspended": 403,
    "not_found": 404,
    "conflict": 409,
    "run_in_progress": 409,
    "idempotency_key_reused": 409,
    "invalid_state": 409,
    "plan_limit_reached": 409,
    "precondition_failed": 412,
    "payload_too_large": 413,
    "unsupported_media_type": 415,
    "validation_failed": 422,
    "unknown_reference": 422,
    "pack_signature_invalid": 422,
    "extension_unavailable": 422,
    "tsa_unavailable": 422,
    "retention_below_minimum": 422,
    "binder_too_large": 422,
    "guest_forbidden": 403,
    "watermark_unsupported": 415,
    "review_required": 409,
    "hold_active": 409,
    "resource_disabled": 423,
    "rate_limited": 429,
    "quota_exceeded": 429,
    "internal_error": 500,
    "upstream_error": 502,
    "unavailable": 503,
    "upstream_timeout": 504,
}


def test_error_codes_match_api_conventions() -> None:
    assert {code.value for code in ErrorCode} == set(_CATALOGUE)
    for name, status in _CATALOGUE.items():
        assert http_status_for(ErrorCode(name)) == status


def test_problem_body_shape() -> None:
    error = NotFoundError("gone")
    body = error.to_problem(instance="/api/v1/agents/1", request_id="req_1")
    assert body["code"] == "not_found"
    assert body["status"] == 404
    assert str(body["type"]).endswith("/not_found")
    assert body["requestId"] == "req_1"


def test_mode_helpers() -> None:
    saas = BaseServiceSettings(deployment_mode=DeploymentMode.SAAS, env=EnvName.DEV)
    single = BaseServiceSettings(deployment_mode=DeploymentMode.SINGLE_TENANT, env=EnvName.DEV)
    assert is_saas(saas)
    assert not is_single_tenant(saas)
    assert is_single_tenant(single)
    assert not is_saas(single)


def test_saas_hashes_user_ids_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_LOG_HASH_USER_IDS", raising=False)
    settings = BaseServiceSettings(deployment_mode=DeploymentMode.SAAS)
    assert settings.log_hash_user_ids


def test_utcnow_is_aware() -> None:
    moment = utcnow()
    assert moment.tzinfo is not None


def test_new_id_is_uuid7() -> None:
    assert new_id().version == 7


@given(
    st.dictionaries(
        st.text(alphabet="abc", min_size=1, max_size=3),
        st.integers(min_value=-5, max_value=5) | st.booleans() | st.none(),
        max_size=4,
    )
)
def test_canonical_json_key_order_invariant(value: dict[str, object]) -> None:
    reversed_keys = dict(reversed(list(value.items())))
    assert canonical_json(value) == canonical_json(reversed_keys)
    assert args_hash(value) == hashlib.sha256(canonical_json(value)).hexdigest()


def test_canonical_json_number_formatting() -> None:
    assert canonical_json({"n": 1}) == canonical_json({"n": 1.0})


def test_cursor_round_trip_and_tamper() -> None:
    cursor_key = "cursor-hmac-key"
    token = encode_cursor(["2026-10-20T00:00:00Z", "0192"], direction="desc", secret=cursor_key)
    keys, direction = decode_cursor(token, secret=cursor_key)
    assert keys == ["2026-10-20T00:00:00Z", "0192"]
    assert direction == "desc"
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(ArError) as caught:
        decode_cursor(tampered, secret=cursor_key)
    assert caught.value.code == ErrorCode.INVALID_CURSOR


def test_keys_include_tenant_or_uuid() -> None:
    sample = uuid.uuid4()
    other = uuid.uuid4()
    for name, func in inspect.getmembers(keymod, inspect.isfunction):
        if name.startswith("_"):
            continue
        hints = get_type_hints(func)
        kwargs = {}
        for param, kind in hints.items():
            if param == "return":
                continue
            if kind is uuid.UUID:
                kwargs[param] = sample if "tenant" in param or param == "jti" else other
            else:
                kwargs[param] = "bucket"
        rendered = func(**kwargs)
        assert str(sample) in rendered or str(other) in rendered


def test_logging_scrubs_secrets() -> None:
    scrubbed = _scrub({"api_key": "super", "nested": {"authorization": "Bearer abc"}, "ok": "fine"})
    assert isinstance(scrubbed, dict)
    assert scrubbed["api_key"] == "[redacted]"
    nested = scrubbed["nested"]
    assert isinstance(nested, dict)
    assert nested["authorization"] == "[redacted]"
    assert scrubbed["ok"] == "fine"


def test_ssrf_blocks_private_and_metadata() -> None:
    assert not is_public_ip("127.0.0.1")
    assert not is_public_ip("169.254.169.254")
    assert not is_public_ip("10.1.1.1")
    assert not is_public_ip("::ffff:127.0.0.1")
    assert is_public_ip("1.1.1.1")

    def resolver(host: str) -> list[str]:
        return ["127.0.0.1"] if host == "evil.test" else ["1.1.1.1"]

    with pytest.raises(ArError):
        assert_public_url("http://evil.test/x", resolver=resolver)
    with pytest.raises(ArError):
        assert_public_url("http://169.254.169.254/", resolver=resolver)
    assert_public_url("http://evil.test/x", resolver=resolver, allow_hosts=["evil.test"])
    assert_public_url("https://ok.test/a", resolver=resolver)


@pytest.mark.asyncio
async def test_internal_jwt_valid_expired_aud_and_replay() -> None:
    private_pem, public_pem = generate_keypair()
    jwks = {"k1": public_pem}
    tenant = uuid.uuid4()
    token = sign_internal_jwt(
        private_pem=private_pem,
        kid="k1",
        iss="runtime-worker",
        aud="model-gateway",
        scopes=sorted(ALLOWED_CALLERS["model-gateway"]["runtime-worker"]),
        tenant_id=tenant,
        ttl_s=60,
    )
    cache = MemoryJtiCache()
    claims = await verify_internal_jwt(
        token, aud="model-gateway", jwks=jwks, cache=cache, allowed_callers=ALLOWED_CALLERS
    )
    assert claims.iss == "runtime-worker"
    assert claims.tenant_id == tenant
    with pytest.raises(ArError) as replayed:
        await verify_internal_jwt(
            token, aud="model-gateway", jwks=jwks, cache=cache, allowed_callers=ALLOWED_CALLERS
        )
    assert replayed.value.code.value == "unauthenticated"
    with pytest.raises(ArError):
        await verify_internal_jwt(
            token,
            aud="mcp-gateway",
            jwks=jwks,
            cache=MemoryJtiCache(),
            allowed_callers=ALLOWED_CALLERS,
        )
    expired = sign_internal_jwt(
        private_pem=private_pem,
        kid="k1",
        iss="api",
        aud="model-gateway",
        scopes=sorted(ALLOWED_CALLERS["model-gateway"]["api"]),
        ttl_s=60,
    )
    with time_machine.travel(timedelta(seconds=120), tick=False), pytest.raises(ArError):
        await verify_internal_jwt(
            expired,
            aud="model-gateway",
            jwks=jwks,
            cache=MemoryJtiCache(),
            allowed_callers=ALLOWED_CALLERS,
        )


def test_request_id_problem_and_readiness() -> None:
    settings = BaseServiceSettings(
        service_name="api", otel_exporter_otlp_endpoint="http://127.0.0.1:9"
    )

    async def broken() -> None:
        raise RuntimeError("down")

    app = create_app("api", settings, readiness_checks={"postgres": broken}, camel_json=True)

    @app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("missing")

    @app.post("/echo")
    async def echo(payload: dict[str, str]) -> dict[str, str]:
        return payload

    client = TestClient(app, raise_server_exceptions=False)
    health = client.get("/healthz", headers={"X-Request-Id": "req_fixed"})
    assert health.status_code == 200
    assert health.headers["x-request-id"] == "req_fixed"
    missing = client.get("/boom")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert missing.json()["code"] == "not_found"
    assert missing.json()["requestId"]
    assert missing.headers["x-request-id"]
    ready = client.get("/readyz")
    assert ready.status_code == 503
    assert ready.json()["failing"] == ["postgres"]
    renamed = client.post("/echo", json={"display_name": "Ava"})
    assert renamed.status_code == 200
    assert renamed.json() == {"displayName": "Ava"}
    invalid = client.post("/echo", json={"n": 1})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_failed"
    too_big = client.post(
        "/echo",
        content=b'{"a":"' + b"x" * 50 + b'"}',
        headers={"content-type": "application/json", "content-length": "99999999"},
    )
    assert too_big.status_code == 413
    assert too_big.json()["code"] == "payload_too_large"


def test_ready_when_checks_pass() -> None:
    settings = BaseServiceSettings(service_name="api")

    def ok() -> None:
        return None

    app = create_app("api", settings, readiness_checks={"self": ok})
    client = TestClient(app)
    assert client.get("/readyz").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_http_client_retries_idempotent(respx_mock: Any) -> None:
    route = respx_mock.get("https://example.com/v1").mock(
        side_effect=[httpx.ConnectError("nope"), httpx.Response(200, json={"ok": True})]
    )

    async def run() -> int:
        client = http_client(resolver=lambda host: ["1.1.1.1"])
        response = await client.request("GET", "https://example.com/v1")
        await client.aclose()
        return response.status_code

    assert asyncio.run(run()) == 200
    assert route.call_count == 2


def test_field_error_round_trip() -> None:
    error = ArError(
        ErrorCode.VALIDATION_FAILED,
        "no",
        errors=[FieldError(loc=["name"], msg="required", type="missing")],
    )
    body = error.to_problem(instance="/", request_id="r")
    errors = body["errors"]
    assert isinstance(errors, list)
    assert errors[0]["msg"] == "required"


def test_payload_too_large_code() -> None:
    assert PayloadTooLargeError().status == 413


def test_setup_logging_does_not_raise() -> None:
    setup_logging(BaseServiceSettings())


def test_cursor_rejects_malformed_token() -> None:
    with pytest.raises(ArError) as caught:
        decode_cursor("not-a-cursor", secret="cursor-hmac-key")  # noqa: S106
    assert caught.value.code == ErrorCode.INVALID_CURSOR


def test_blocked_literal_ip_is_rejected() -> None:
    with pytest.raises(ArError):
        assert_public_url("http://127.0.0.1/secret")
    with pytest.raises(ArError):
        assert_public_url("ftp://example.com")


def test_valkey_client_factory() -> None:
    client = valkey_client("redis://localhost:6379/0")
    assert client is not None


def test_s3_put_and_presign(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = BaseServiceSettings(
        s3_access_key_id="dev",
        s3_secret_access_key="dev-secret",  # noqa: S106
    )
    store = S3Store(settings)

    class _Client:
        async def put_object(self, **kwargs: object) -> None:
            assert kwargs["Key"] == "a.txt"

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    class _Session:
        def create_client(self, name: str, **kwargs: object) -> _Client:
            assert name == "s3"
            return _Client()

    store._session = _Session()  # type: ignore[assignment]

    async def run() -> str:
        await store.put_bytes("a.txt", b"hi", "text/plain")
        return await store.presign_get("a.txt")

    url = asyncio.run(run())
    assert "a.txt" in url


def test_serve_uvicorn_and_granian(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append("uvicorn")

    class _Server:
        def __init__(self, target: str, **kwargs: object) -> None:
            calls.append(target)

        def serve(self) -> None:
            calls.append("granian")

    monkeypatch.setenv("AR_APP_MODULE", "ar_api.main")
    monkeypatch.setenv("AR_PORT", "8000")
    monkeypatch.setattr(serve.uvicorn, "run", fake_run)
    monkeypatch.setattr(serve, "Server", _Server)
    monkeypatch.setattr(serve, "get_settings", lambda: BaseServiceSettings(asgi_server="uvicorn"))
    serve.main()
    monkeypatch.setattr(serve, "get_settings", lambda: BaseServiceSettings(asgi_server="granian"))
    serve.main()
    assert "uvicorn" in calls
    assert "granian" in calls


def test_serve_module_entrypoint_starts_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """``python -m ar_common.serve`` must call ``main``; otherwise containers exit 0."""
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["port"] = kwargs.get("port")

    monkeypatch.setenv("AR_APP_MODULE", "ar_api.main")
    monkeypatch.setenv("AR_PORT", "8123")
    monkeypatch.setattr(serve.uvicorn, "run", fake_run)
    previous = get_settings()
    set_settings(BaseServiceSettings(asgi_server="uvicorn"))
    try:
        runpy.run_module("ar_common.serve", run_name="__main__")
    finally:
        set_settings(previous)
    assert captured["port"] == 8123
