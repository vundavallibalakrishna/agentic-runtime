"""Named connections. The secret is encrypted and never returned."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from base64 import b64encode
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.secrets.crypto import open_sealed, seal
from ar_domain.tools.http_tools import fetch_text, guard_public

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_KINDS = {
    "api_key",
    "bearer",
    "basic",
    "oauth_authorization_code",
    "oauth_client_credentials",
}
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$")


def connection_key() -> bytes:
    """Key for connection secrets. Derived from the cursor secret, never logged."""
    raw = os.environ.get("AR_CURSOR_SECRET", "dev-cursor-secret")
    return hashlib.sha256(b"ar-connection-v1:" + raw.encode()).digest()


def headers_for(
    store: Any, tenant_id: object, user_id: object, name: str
) -> tuple[dict[str, str], str]:
    """Resolve one connection to request headers and the secret to scrub."""
    row = _find(store, tenant_id, user_id, name)
    if row is None:
        raise ArError(ErrorCode.NOT_FOUND, f"No connection named {name} is available to you.")
    if str(row.get("status")) == "revoked":
        raise ArError(ErrorCode.FORBIDDEN, f"Connection {name} was revoked.")
    _refresh_if_needed(store, row)
    if _expired(row) and str(row.get("kind")) not in {
        "oauth_authorization_code",
        "oauth_client_credentials",
    }:
        row["status"] = "expired"
        _audit_row(store, row, "connection.expired")
        raise ArError(ErrorCode.FORBIDDEN, f"Connection {name} has expired. Rotate it.")
    return _headers(row)


class ConnectionBook:
    """Owner-scoped credentials for HTTP, MCP and imported APIs."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_items(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            _view(row)
            for row in _book(self.store).values()
            if row.get("tenant_id") == actor.tenant_id and row.get("owner_user_id") == actor.user_id
        ]
        return sorted(rows, key=lambda item: str(item["name"]).lower())

    def get(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        return _view(self._own(actor, connection_id))

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        name = str(body.get("name") or "").strip()
        kind = str(body.get("kind") or "")
        if not _NAME.match(name):
            raise ValidationFailedError("name must start with a letter and stay short")
        if kind not in _KINDS:
            raise ValidationFailedError(
                "kind must be api_key, bearer, basic, oauth_authorization_code "
                "or oauth_client_credentials"
            )
        if any(
            row.get("tenant_id") == actor.tenant_id and str(row.get("name")).lower() == name.lower()
            for row in _book(self.store).values()
        ):
            raise ConflictError("a connection with that name already exists")
        secret = str(body.get("secret") or "")
        if kind != "oauth_authorization_code" and not secret:
            raise ValidationFailedError("secret is required")
        if kind == "basic" and not str(body.get("username") or "").strip():
            raise ValidationFailedError("username is required for basic auth")
        if kind.startswith("oauth_") and not str(body.get("token_url") or "").strip():
            raise ValidationFailedError("tokenUrl is required for OAuth")
        if kind == "oauth_authorization_code" and not str(body.get("authorize_url") or "").strip():
            raise ValidationFailedError("authorizeUrl is required")
        row = self._row(actor, name, kind, body, secret)
        _book(self.store)[row["id"]] = row
        _audit(self.store, actor, "connection.created", row["id"], {"name": name, "kind": kind})
        return _view(row)

    def update(
        self, actor: Actor, connection_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._own(actor, connection_id)
        for key in (
            "header_name",
            "username",
            "token_url",
            "authorize_url",
            "client_id",
            "probe_url",
        ):
            if key in body and body[key] is not None:
                row[key] = str(body[key])
        scopes = body.get("scopes")
        if isinstance(scopes, list):
            row["scopes"] = [str(item) for item in scopes]
        if body.get("expires_at"):
            row["expires_at"] = str(body["expires_at"])
        row["updated_at"] = utcnow()
        _audit(self.store, actor, "connection.updated", connection_id, {"name": row.get("name")})
        return _view(row)

    def rotate(self, actor: Actor, connection_id: uuid.UUID, secret: str) -> dict[str, object]:
        row = self._own(actor, connection_id)
        if not secret:
            raise ValidationFailedError("secret is required")
        sealed = _seal(secret)
        if secret.encode() in sealed:
            raise ArError(ErrorCode.INTERNAL_ERROR, "connection secret was not encrypted")
        row["secret"] = sealed
        row["access_token"] = b""
        row["refresh_token"] = b""
        current = row.get("version")
        row["version"] = (current if isinstance(current, int) else 1) + 1
        row["status"] = "active"
        row["updated_at"] = utcnow()
        _audit(self.store, actor, "connection.rotated", connection_id, {"name": row.get("name")})
        return _view(row)

    def revoke(self, actor: Actor, connection_id: uuid.UUID) -> None:
        row = self._own(actor, connection_id)
        row["status"] = "revoked"
        row["secret"] = b""
        row["access_token"] = b""
        row["refresh_token"] = b""
        row["updated_at"] = utcnow()
        _audit(self.store, actor, "connection.revoked", connection_id, {"name": row.get("name")})

    def test(self, actor: Actor, connection_id: uuid.UUID, url: str = "") -> dict[str, object]:
        row = self._own(actor, connection_id)
        target = url.strip() or str(row.get("probe_url") or "")
        try:
            _refresh_if_needed(self.store, row)
            headers, secret = _headers(row)
        except ArError as exc:
            row["last_error"] = str(exc)
            row["last_tested_at"] = utcnow()
            return {"ok": False, "status": 0, "error": str(exc)}
        if not target:
            if str(row.get("kind")) == "oauth_client_credentials":
                row["last_error"] = None
                row["last_tested_at"] = utcnow()
                row["status"] = "active"
                _audit(self.store, actor, "connection.tested", connection_id, {"ok": True})
                return {"ok": True, "status": 0, "error": None}
            return {
                "ok": False,
                "status": 0,
                "error": "Add a test URL. The secret is not sent anywhere until you do.",
            }
        problem = guard_public(target, allow=["*"], loopback=False)
        if problem:
            row["last_error"] = problem
            row["last_tested_at"] = utcnow()
            return {"ok": False, "status": 0, "error": problem}
        try:
            status, body = fetch_text(self.store, "GET", target, headers=headers, timeout=20)
        except httpx.HTTPError:
            row["last_error"] = "the host did not answer"
            row["last_tested_at"] = utcnow()
            return {"ok": False, "status": 0, "error": "the host did not answer"}
        snippet = _scrub(body[:200], secret)
        ok = 200 <= status < 400
        row["last_error"] = None if ok else f"HTTP {status}"
        row["last_tested_at"] = utcnow()
        row["status"] = "active" if ok else str(row.get("status") or "active")
        _audit(
            self.store,
            actor,
            "connection.tested",
            connection_id,
            {"ok": ok, "status": status},
        )
        return {
            "ok": ok,
            "status": status,
            "error": None if ok else f"HTTP {status}",
            "snippet": snippet,
        }

    def start(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        row = self._own(actor, connection_id)
        if str(row.get("kind")) != "oauth_authorization_code":
            raise ValidationFailedError(
                "only an authorization-code connection has an authorize URL"
            )
        verifier = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(18)
        self.store.oauth_states[state] = {
            "kind": "service_connection",
            "connection_id": connection_id,
            "user_id": actor.user_id,
            "tenant_id": actor.tenant_id,
            "verifier": verifier,
        }
        scopes = row.get("scopes")
        scope = " ".join(str(item) for item in scopes) if isinstance(scopes, list) else ""
        query = urlencode(
            {
                "response_type": "code",
                "client_id": str(row.get("client_id") or "ar"),
                "state": state,
                "code_challenge": _challenge(verifier),
                "code_challenge_method": "S256",
                "scope": scope,
            }
        )
        base = str(row.get("authorize_url") or "")
        return {"authorize_url": f"{base}?{query}", "state": state}

    async def callback(self, code: str, state: str) -> dict[str, object]:
        saved = self.store.oauth_states.pop(state, None)
        if not isinstance(saved, dict) or saved.get("kind") != "service_connection":
            raise ArError(ErrorCode.BAD_REQUEST, "unknown oauth state")
        connection_id = saved.get("connection_id")
        row = _book(self.store).get(connection_id)
        if not isinstance(row, dict):
            raise NotFoundError()
        tokens = await _exchange(row, code, str(saved.get("verifier") or ""))
        _store_tokens(row, tokens)
        row["status"] = "active"
        row["updated_at"] = utcnow()
        self.store.audit_log.append(
            {
                "tenant_id": str(saved.get("tenant_id")),
                "actor_id": str(saved.get("user_id")),
                "action": "connection.updated",
                "target_type": "service_connection",
                "target_id": str(connection_id),
                "detail": {"name": row.get("name")},
                "outcome": "success",
                "at": utcnow().isoformat(),
            }
        )
        return _view(row)

    def _own(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        row = _book(self.store).get(connection_id)
        if (
            not isinstance(row, dict)
            or row.get("tenant_id") != actor.tenant_id
            or row.get("owner_user_id") != actor.user_id
        ):
            raise NotFoundError()
        return row

    def _row(
        self,
        actor: Actor,
        name: str,
        kind: str,
        body: dict[str, object],
        secret: str,
    ) -> dict[str, object]:
        sealed = _seal(secret) if secret else b""
        if secret and secret.encode() in sealed:
            raise ArError(ErrorCode.INTERNAL_ERROR, "connection secret was not encrypted")
        now = utcnow()
        scopes = body.get("scopes")
        scope_list = [str(item) for item in scopes] if isinstance(scopes, list) else []
        return {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "owner_user_id": actor.user_id,
            "name": name,
            "kind": kind,
            "status": "active",
            "header_name": str(body.get("header_name") or "X-API-Key"),
            "username": str(body.get("username") or ""),
            "token_url": str(body.get("token_url") or ""),
            "authorize_url": str(body.get("authorize_url") or ""),
            "client_id": str(body.get("client_id") or ""),
            "scopes": scope_list,
            "probe_url": str(body.get("probe_url") or ""),
            "secret": sealed,
            "access_token": b"",
            "refresh_token": b"",
            "expires_at": str(body.get("expires_at") or "") or None,
            "last_tested_at": None,
            "last_error": None,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }


def _book(store: Any) -> dict[Any, dict[str, object]]:
    book = getattr(store, "service_connections", None)
    if not isinstance(book, dict):
        store.service_connections = {}
        book = store.service_connections
    return book


def _find(store: Any, tenant_id: object, user_id: object, name: str) -> dict[str, object] | None:
    for row in _book(store).values():
        if (
            row.get("tenant_id") == tenant_id
            and row.get("owner_user_id") == user_id
            and str(row.get("name")).lower() == name.lower()
        ):
            return row
    return None


def _view(row: dict[str, object]) -> dict[str, object]:
    """Public shape. Ciphertext and token fields stay off the wire."""
    owner = row.get("owner_user_id")
    return {
        "id": str(row["id"]),
        "name": row.get("name"),
        "kind": row.get("kind"),
        "status": "expired" if _expired(row) else row.get("status"),
        "header_name": row.get("header_name") or "",
        "username": row.get("username") or "",
        "token_url": row.get("token_url") or "",
        "authorize_url": row.get("authorize_url") or "",
        "client_id": row.get("client_id") or "",
        "scopes": scopes if isinstance(scopes := row.get("scopes"), list) else [],
        "probe_url": row.get("probe_url") or "",
        "expires_at": row.get("expires_at"),
        "last_tested_at": _iso(row.get("last_tested_at")),
        "last_error": row.get("last_error"),
        "version": row.get("version") or 1,
        "has_secret": bool(row.get("secret")),
        "owner": None if owner is None else {"id": str(owner)},
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _headers(row: dict[str, object]) -> tuple[dict[str, str], str]:
    kind = str(row.get("kind"))
    if kind in {"oauth_authorization_code", "oauth_client_credentials"}:
        token = _open(row.get("access_token"))
        if not token:
            raise ArError(ErrorCode.FORBIDDEN, "this connection has no access token yet")
        return {"Authorization": f"Bearer {token}"}, token
    secret = _open(row.get("secret"))
    if not secret:
        raise ArError(ErrorCode.FORBIDDEN, "this connection has no secret")
    if kind == "bearer":
        return {"Authorization": f"Bearer {secret}"}, secret
    if kind == "basic":
        username = str(row.get("username") or "")
        token = b64encode(f"{username}:{secret}".encode()).decode()
        return {"Authorization": f"Basic {token}"}, secret
    header = str(row.get("header_name") or "X-API-Key")
    return {header: secret}, secret


def _refresh_if_needed(store: Any, row: dict[str, object]) -> None:
    kind = str(row.get("kind"))
    if kind == "oauth_client_credentials" and (_expired(row) or not _open(row.get("access_token"))):
        tokens = _client_credentials(row)
        _store_tokens(row, tokens)
        return
    if kind == "oauth_authorization_code" and _expired(row) and _open(row.get("refresh_token")):
        tokens = _refresh_token(row)
        _store_tokens(row, tokens)
        del store


def _client_credentials(row: dict[str, object]) -> dict[str, str]:
    token_url = str(row.get("token_url") or "")
    if token_url.startswith("memory://"):
        return {"access_token": f"access-{row.get('name')}", "expires_in": "3600"}
    problem = guard_public(token_url, allow=["*"], loopback=False)
    if problem:
        raise ArError(ErrorCode.FORBIDDEN, problem)
    form = {
        "grant_type": "client_credentials",
        "client_id": str(row.get("client_id") or ""),
        "client_secret": _open(row.get("secret")),
    }
    return _token_response(token_url, form)


def _refresh_token(row: dict[str, object]) -> dict[str, str]:
    token_url = str(row.get("token_url") or "")
    if token_url.startswith("memory://"):
        return {"access_token": f"refreshed-{row.get('name')}", "expires_in": "3600"}
    problem = guard_public(token_url, allow=["*"], loopback=False)
    if problem:
        raise ArError(ErrorCode.FORBIDDEN, problem)
    form = {
        "grant_type": "refresh_token",
        "refresh_token": _open(row.get("refresh_token")),
        "client_id": str(row.get("client_id") or ""),
        "client_secret": _open(row.get("secret")),
    }
    return _token_response(token_url, form)


def _token_response(token_url: str, form: dict[str, str]) -> dict[str, str]:
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(token_url, data=form)
            response.raise_for_status()
            loaded = response.json()
    except httpx.HTTPError as exc:
        raise ArError(ErrorCode.UPSTREAM_ERROR, "the token endpoint did not answer") from exc
    if not isinstance(loaded, dict) or not loaded.get("access_token"):
        raise ArError(ErrorCode.UPSTREAM_ERROR, "the token endpoint returned no access token")
    return {str(key): str(value) for key, value in loaded.items() if value is not None}


async def _exchange(row: dict[str, object], code: str, verifier: str) -> dict[str, str]:
    token_url = str(row.get("token_url") or "")
    if code == "invalid":
        raise ArError(ErrorCode.BAD_REQUEST, "invalid_grant")
    if token_url.startswith("memory://"):
        return {
            "access_token": f"access-{code}",
            "refresh_token": f"refresh-{code}",
            "expires_in": "3600",
        }
    problem = guard_public(token_url, allow=["*"], loopback=False)
    if problem:
        raise ArError(ErrorCode.FORBIDDEN, problem)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": str(row.get("client_id") or ""),
        "client_secret": _open(row.get("secret")),
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(token_url, data=form)
            response.raise_for_status()
            loaded = response.json()
    except httpx.HTTPError as exc:
        raise ArError(ErrorCode.UPSTREAM_ERROR, "the token endpoint did not answer") from exc
    if not isinstance(loaded, dict) or not loaded.get("access_token"):
        raise ArError(ErrorCode.UPSTREAM_ERROR, "the token endpoint returned no access token")
    return {str(key): str(value) for key, value in loaded.items() if value is not None}


def _store_tokens(row: dict[str, object], tokens: dict[str, str]) -> None:
    access = tokens.get("access_token") or ""
    refresh = tokens.get("refresh_token") or ""
    row["access_token"] = _seal(access) if access else row.get("access_token") or b""
    if refresh:
        row["refresh_token"] = _seal(refresh)
    expires_in = tokens.get("expires_in")
    if expires_in and str(expires_in).isdigit():
        row["expires_at"] = (utcnow() + timedelta(seconds=int(expires_in))).isoformat()
    row["updated_at"] = utcnow()


def _expired(row: dict[str, object]) -> bool:
    raw = row.get("expires_at")
    if not isinstance(raw, str) or not raw:
        return False
    try:
        from datetime import datetime  # noqa: PLC0415

        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if stamp.tzinfo is None:
        return False
    return stamp <= utcnow()


def _seal(value: str) -> bytes:
    if not value:
        return b""
    return seal(connection_key(), value.encode())


def _open(blob: object) -> str:
    if not isinstance(blob, bytes) or not blob:
        return ""
    try:
        return open_sealed(connection_key(), blob).decode()
    except Exception as exc:  # noqa: BLE001 — a bad blob is an empty secret, not a crash
        del exc
        return ""


def _scrub(text: str, secret: str) -> str:
    if secret and len(secret) >= 4:
        return text.replace(secret, "[redacted]")
    return text


def _challenge(verifier: str) -> str:
    import base64  # noqa: PLC0415

    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _iso(value: object) -> str | None:
    if value is None:
        return None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return str(iso())
    return str(value)


def _audit(
    store: Any, actor: Actor, action: str, target_id: object, detail: dict[str, object]
) -> None:
    store.audit_log.append(
        {
            "tenant_id": str(actor.tenant_id),
            "actor_id": str(actor.user_id),
            "action": action,
            "target_type": "service_connection",
            "target_id": str(target_id),
            "detail": detail,
            "outcome": "success",
            "at": utcnow().isoformat(),
        }
    )


def _audit_row(store: Any, row: dict[str, object], action: str) -> None:
    store.audit_log.append(
        {
            "tenant_id": str(row.get("tenant_id")),
            "actor_id": str(row.get("owner_user_id")),
            "action": action,
            "target_type": "service_connection",
            "target_id": str(row.get("id")),
            "detail": {"name": row.get("name")},
            "outcome": "failure",
            "at": utcnow().isoformat(),
        }
    )
