"""Exchange a stored secret for a short-lived token.

The body is a POST. The secret is never placed on a query string. Header name
and the JSON field names come from the connection, not from a vendor branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ar_common.egress_http import EgressDenied, sync_client
from ar_common.errors import ArError, ErrorCode
from ar_common.offload import blocking
from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def request_body(row: dict[str, object], secret: str) -> dict[str, str]:
    """JSON body. Field names are on the connection. Older rows stored them in ``authorize_url``."""
    user_field = str(row.get("exchange_user_field") or "")
    secret_field = str(row.get("exchange_secret_field") or "")
    if not user_field or not secret_field:
        spec = str(row.get("authorize_url") or "username:password")
        user_field, _, rest = spec.partition(":")
        secret_field, _, _extra = rest.partition(":")
    return {
        user_field or "username": str(row.get("username") or ""),
        secret_field or "password": secret,
    }


def headers_for_token(row: dict[str, object], token: str) -> dict[str, str]:
    """Headers for calls after the exchange. A non-Authorization header has no prefix."""
    header = str(row.get("header_name") or "Authorization")
    prefix = "Bearer " if header.lower() == "authorization" else ""
    headers = {header: f"{prefix}{token}"}
    extra = str(row.get("exchange_extra_header") or "")
    if not extra:
        parts = str(row.get("authorize_url") or "").split(":")
        extra = parts[2] if len(parts) > 2 else ""
    client = str(row.get("client_id") or "")
    if extra and client:
        headers[extra] = client
    return headers


def cached_token(store: Any, row: dict[str, object]) -> str:
    book = getattr(store, "exchange_cache", None)
    if not isinstance(book, dict):
        return ""
    found = book.get(str(row.get("id")))
    if not isinstance(found, dict):
        return ""
    until = str(found.get("until") or "")
    token = str(found.get("token") or "")
    if token and until > utcnow().isoformat():
        return token
    return ""


def remember(store: Any, row: dict[str, object], token: str, seconds: int) -> None:
    book = getattr(store, "exchange_cache", None)
    if not isinstance(book, dict):
        book = {}
        store.exchange_cache = book
    from datetime import timedelta  # noqa: PLC0415

    book[str(row.get("id"))] = {
        "token": token,
        "until": (utcnow() + timedelta(seconds=max(60, seconds))).isoformat(),
    }


def forget(store: Any, row: dict[str, object]) -> None:
    """Drop a cached token. Called when the secret changes or the server returns 401."""
    book = getattr(store, "exchange_cache", None)
    if isinstance(book, dict):
        book.pop(str(row.get("id")), None)


def exchange(store: Any, row: dict[str, object], secret: str) -> str:
    """POST the secret and return the token. A cached token is reused."""
    found = cached_token(store, row)
    if found:
        return found
    url = str(row.get("token_url") or "")
    if not url:
        raise ArError(ErrorCode.FORBIDDEN, "this connection has no token URL")
    body = request_body(row, secret)
    from ar_common.egress_http import bind_allow, reset_allow  # noqa: PLC0415
    from ar_domain.egress import current_tenant, dial_allow  # noqa: PLC0415

    transport = getattr(store, "connector_transport", None)
    allow_token = bind_allow(dial_allow(store, current_tenant()))
    try:
        try:
            kwargs: dict[str, object] = {"timeout": 10.0}
            if transport is not None:
                kwargs["transport"] = transport
            with sync_client(**kwargs) as client:  # type: ignore[arg-type]
                response = blocking(client.post, url, json=body)
        except (httpx.HTTPError, EgressDenied) as exc:
            raise ArError(
                ErrorCode.UNAVAILABLE, f"token exchange failed ({type(exc).__name__})"
            ) from exc
        if response.status_code == 401:
            forget(store, row)
            raise ArError(ErrorCode.FORBIDDEN, "token exchange answered 401")
        if response.status_code >= 300:
            raise ArError(ErrorCode.FORBIDDEN, f"token exchange answered {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ArError(ErrorCode.FORBIDDEN, "token exchange did not return an object")
        token = str(
            payload.get("token") or payload.get("access_token") or payload.get("accessToken") or ""
        )
        if not token:
            raise ArError(ErrorCode.FORBIDDEN, "token exchange returned no token")
        raw_life = payload.get("expires_in") or payload.get("expiresIn") or 86400
        try:
            life = int(raw_life)
        except TypeError, ValueError:
            life = 86400
        remember(store, row, token, life)
        return token
    finally:
        reset_allow(allow_token)
