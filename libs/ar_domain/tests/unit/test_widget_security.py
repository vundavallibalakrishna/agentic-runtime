"""Host token and frame-policy regressions for embedded chat."""

import base64
import hashlib
import hmac

import orjson
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ar_common.time import utcnow
from ar_domain.channels.widget_auth import (
    allowed_origins,
    verify_rsa_widget_token,
    verify_widget_token,
)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _signed(
    payload: dict[str, object],
    *,
    algorithm: str = "HS256",
    secret: str = "host-secret",  # noqa: S107
) -> str:
    signing = f"{_b64(orjson.dumps({'alg': algorithm}))}.{_b64(orjson.dumps(payload))}"
    return (
        signing + "." + _b64(hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest())
    )


@pytest.mark.parametrize(
    "change",
    [
        {"exp": 0},
        {"exp": True},
        {"exp": "100"},
        {"exp": None},
        {"aud": "another-widget"},
        {"sub": ""},
        {"sub": ["admin"]},
    ],
)
def test_widget_claims_fail_closed(change: dict[str, object]) -> None:
    claims = {
        "aud": "widget",
        "sub": "admin@example.test",
        "exp": int(utcnow().timestamp()) + 60,
        **change,
    }
    assert verify_widget_token(_signed(claims), "host-secret", "widget") is None


def test_widget_algorithm_secret_and_lifetime_are_enforced() -> None:
    claims = {"aud": "widget", "sub": "admin@example.test", "exp": int(utcnow().timestamp()) + 60}
    assert verify_widget_token(_signed(claims), "host-secret", "widget") == claims
    assert verify_widget_token(_signed(claims, algorithm="none"), "host-secret", "widget") is None
    assert verify_widget_token(_signed(claims, secret=""), "", "widget") is None
    assert (
        verify_widget_token(
            _signed({**claims, "exp": int(utcnow().timestamp()) + 601}), "host-secret", "widget"
        )
        is None
    )
    assert (
        verify_widget_token(
            _signed({**claims, "nbf": int(utcnow().timestamp()) + 60}), "host-secret", "widget"
        )
        is None
    )
    for invalid in ("a.b.c", "bad", "é.é.é", "W10.W10.W10"):
        assert verify_widget_token(invalid, "host-secret", "widget") is None


def test_registered_rsa_key_only() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()
    claims = {"aud": "widget", "sub": "admin@example.test", "exp": int(utcnow().timestamp()) + 60}
    signing = (
        f"{_b64(orjson.dumps({'alg': 'RS256', 'kid': 'portal'}))}.{_b64(orjson.dumps(claims))}"
    )
    token = signing + "." + _b64(key.sign(signing.encode(), padding.PKCS1v15(), hashes.SHA256()))
    jwk = {
        "kty": "RSA",
        "kid": "portal",
        "n": _b64(public.n.to_bytes(256)),
        "e": _b64(public.e.to_bytes(3)),
    }
    assert verify_rsa_widget_token(token, {"keys": [jwk]}, "widget") == claims
    assert verify_rsa_widget_token(token, {"keys": [{**jwk, "kid": "other"}]}, "widget") is None
    assert verify_rsa_widget_token(token, {"keys": [{**jwk, "use": "enc"}]}, "widget") is None
    assert verify_rsa_widget_token(token[:-10] + "AAAAAAAAAA", {"keys": [jwk]}, "widget") is None


def test_frame_policy_rejects_csp_injection_and_origin_prefixes() -> None:
    origins = [
        "https://portal.example",
        "http://localhost:3101",
        "https://portal.example",
        "https://evil.test; script-src *",
        "http://localhost.evil.test",
        "https://user@portal.example",
        "https://portal.example/path",
        "https://*.example",
        "https://portal.example:bad",
        "https://portal.example\\evil",
        "https://portal.example\nhttps://evil.test",
    ]
    assert allowed_origins({"allowedOrigins": origins}) == [
        "https://portal.example",
        "http://localhost:3101",
    ]
    assert allowed_origins({"allowed_origins": "*"}) == []


@pytest.mark.parametrize(
    "response_kind", ["invalid_url", "oversized", "unavailable", "malformed", "blocked", "valid"]
)
async def test_registered_jwks_fetch_fails_closed(
    response_kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    import httpx

    from ar_common.errors import ForbiddenError
    from ar_domain.channels.widget_auth import verify_registered_token

    client = AsyncMock()
    response = httpx.Response(200, json={"keys": []})
    if response_kind == "oversized":
        response = httpx.Response(200, content=b"x" * 65537)
    elif response_kind == "unavailable":
        response = httpx.Response(503)
    elif response_kind == "malformed":
        response = httpx.Response(200, content=b"invalid")
    elif response_kind == "blocked":
        client.request.side_effect = ForbiddenError("blocked destination")
    client.request.return_value = response
    monkeypatch.setattr("ar_domain.channels.widget_auth.http_client", lambda: client)
    url = (
        "http://insecure.example/jwks"
        if response_kind == "invalid_url"
        else "https://portal.example/jwks"
    )
    assert (
        await verify_registered_token(
            "invalid", secret="", audience="widget", config={"jwksUrl": url}
        )
        is None
    )
    if response_kind == "invalid_url":
        client.request.assert_not_called()
    else:
        client.request.assert_awaited_once_with("GET", url, timeout=5)
        client.aclose.assert_awaited_once()


def test_paid_plan_capability_does_not_enable_widget_for_new_tenants() -> None:
    from ar_contracts.tenants import TenantSettings
    from ar_domain.identity.seed import plan_limits

    assert plan_limits("enterprise")["features"]["widget"] is True
    assert plan_limits("self_hosted")["features"]["widget"] is True
    assert plan_limits("free")["features"]["widget"] is False
    assert TenantSettings().features.widget is False
