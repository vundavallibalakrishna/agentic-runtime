"""Credential providers, OAuth grants and encrypted token cache.

The cache stands in for Valkey until the dev API uses a shared store (OQ-31).
"""

import base64
import hashlib
import secrets
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlencode

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.tools.logic import as_sequence

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_KEY = hashlib.sha256(b"ar-dev-token-cache").digest()


class CredentialBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_providers(self, actor: Actor) -> list[dict[str, object]]:
        return [
            self._provider_view(row)
            for row in self.store.credential_providers.values()
            if row.get("tenant_id") == actor.tenant_id
        ]

    def create_provider(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        slug = str(body.get("slug") or "")
        if not slug:
            raise ValidationFailedError("slug is required")
        if any(
            row.get("tenant_id") == actor.tenant_id and row.get("slug") == slug
            for row in self.store.credential_providers.values()
        ):
            raise ConflictError("a provider with that slug already exists")
        provider_id = new_id()
        now = utcnow()
        self.store.credential_providers[provider_id] = {
            "id": provider_id,
            "tenant_id": actor.tenant_id,
            "slug": slug,
            "name": str(body.get("name") or slug),
            "kind": str(body.get("kind") or "oauth2"),
            "authorize_url": body.get("authorize_url"),
            "token_url": body.get("token_url"),
            "client_id": body.get("client_id"),
            "default_scopes": as_sequence(body.get("default_scopes")),
            "token_exchange_audience": body.get("token_exchange_audience"),
            "extra": body.get("extra") if isinstance(body.get("extra"), dict) else {},
            "status": "active",
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self._audit(actor, "credential_provider.created", provider_id)
        return self._provider_view(self.store.credential_providers[provider_id])

    def patch_provider(
        self, actor: Actor, provider_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._provider(actor, provider_id)
        for key in ("name", "authorize_url", "token_url", "client_id", "status", "extra"):
            if key in body and body[key] is not None:
                row[key] = body[key]
        row["updated_at"] = utcnow()
        self._audit(actor, "credential_provider.updated", provider_id)
        return self._provider_view(row)

    def delete_provider(self, actor: Actor, provider_id: uuid.UUID) -> None:
        self._provider(actor, provider_id)
        self.store.credential_providers.pop(provider_id, None)
        self._audit(actor, "credential_provider.deleted", provider_id)

    def list_connections(self, actor: Actor) -> list[dict[str, object]]:
        rows = []
        for row in self.store.credential_grants.values():
            if row.get("tenant_id") == actor.tenant_id and row.get("user_id") == actor.user_id:
                rows.append(self._grant_view(row))  # noqa: PERF401
        return rows

    def start(self, actor: Actor, provider_id: uuid.UUID) -> dict[str, object]:
        provider = self._provider(actor, provider_id)
        verifier = secrets.token_urlsafe(32)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state = secrets.token_urlsafe(18)
        self.store.oauth_states[state] = {
            "provider_id": provider_id,
            "user_id": actor.user_id,
            "tenant_id": actor.tenant_id,
            "verifier": verifier,
        }
        query = urlencode(
            {
                "response_type": "code",
                "client_id": str(provider.get("client_id") or "ar"),
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": " ".join(
                    str(item) for item in as_sequence(provider.get("default_scopes"))
                ),
            }
        )
        base = str(provider.get("authorize_url") or "")
        return {"authorize_url": f"{base}?{query}", "state": state}

    async def callback(self, code: str, state: str) -> dict[str, object]:
        saved = self.store.oauth_states.pop(state, None)
        if not isinstance(saved, dict):
            raise ArError(ErrorCode.BAD_REQUEST, "unknown oauth state")
        provider = self.store.credential_providers.get(saved["provider_id"])
        if not isinstance(provider, dict):
            raise NotFoundError()
        tokens = await self._exchange(provider, code, str(saved["verifier"]))
        grant = self._upsert_grant(saved, provider, tokens)
        self.store.audit_log.append(
            {
                "tenant_id": str(saved["tenant_id"]),
                "actor_id": str(saved["user_id"]),
                "action": "connection.created",
                "target_type": "credential_grant",
                "target_id": str(grant["id"]),
                "detail": {},
                "outcome": "success",
                "at": utcnow().isoformat(),
            }
        )
        return self._grant_view(grant)

    def disconnect(self, actor: Actor, grant_id: uuid.UUID) -> None:
        row = self.store.credential_grants.get(grant_id)
        if (
            not isinstance(row, dict)
            or row.get("tenant_id") != actor.tenant_id
            or row.get("user_id") != actor.user_id
        ):
            raise NotFoundError()
        row["status"] = "revoked"
        row["refresh_token"] = ""
        self._audit(actor, "connection.revoked", grant_id)

    async def access_token_for(self, actor: Actor, provider_id: uuid.UUID) -> str:
        grant = self._grant_for(actor, provider_id)
        if grant is None or grant.get("status") != "active":
            raise ArError(ErrorCode.FORBIDDEN, "credential_required")
        cache_key = f"{actor.tenant_id}:{actor.user_id}:{provider_id}"
        cached = self.store.token_cache.get(cache_key)
        if isinstance(cached, bytes):
            opened = _open(cached)
            if opened:
                return opened
        refreshed = await self._refresh(grant)
        sealed = _seal(refreshed)
        self.store.token_cache[cache_key] = sealed
        if refreshed.encode() in sealed:
            raise ArError(ErrorCode.INTERNAL_ERROR, "token cache leaked plaintext")
        grant["last_used_at"] = utcnow()
        return refreshed

    def _grant_for(self, actor: Actor, provider_id: uuid.UUID) -> dict[str, object] | None:
        for row in self.store.credential_grants.values():
            if (
                row.get("user_id") == actor.user_id
                and row.get("provider_id") == provider_id
                and row.get("tenant_id") == actor.tenant_id
            ):
                return cast("dict[str, object]", row)
        return None

    async def _exchange(
        self, provider: dict[str, object], code: str, verifier: str
    ) -> dict[str, str]:
        if code == "invalid":
            raise ArError(ErrorCode.BAD_REQUEST, "invalid_grant")
        token_url = str(provider.get("token_url") or "")
        if token_url.startswith("memory://"):
            return {"access_token": f"access-{code}", "refresh_token": f"refresh-{code}"}
        kind = str(provider.get("kind"))
        form = {"code": code, "code_verifier": verifier, "grant_type": "authorization_code"}
        if kind == "token_exchange":
            form = {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": code,
                "audience": str(provider.get("token_exchange_audience") or ""),
            }
        return await _post_token(token_url, form, self.store)

    async def _refresh(self, grant: dict[str, object]) -> str:
        provider = self.store.credential_providers.get(grant.get("provider_id"))
        refresh = str(grant.get("refresh_token") or "")
        if not isinstance(provider, dict):
            raise ArError(ErrorCode.FORBIDDEN, "credential_required")
        token_url = str(provider.get("token_url") or "")
        if token_url.startswith("memory://"):
            rotated = f"refresh-rotated-{refresh[-6:]}"
            grant["refresh_token"] = rotated
            grant["access_token"] = f"access-{rotated}"
            return str(grant["access_token"])
        try:
            tokens = await _post_token(
                token_url,
                {"grant_type": "refresh_token", "refresh_token": refresh},
                self.store,
            )
        except ArError as exc:
            grant["status"] = "error"
            raise ArError(ErrorCode.BAD_REQUEST, "invalid_grant") from exc
        if tokens.get("refresh_token"):
            grant["refresh_token"] = tokens["refresh_token"]
        return tokens["access_token"]

    def _upsert_grant(
        self, saved: dict[str, object], provider: dict[str, object], tokens: dict[str, str]
    ) -> dict[str, object]:
        for row in self.store.credential_grants.values():
            if row.get("user_id") == saved["user_id"] and row.get("provider_id") == provider["id"]:
                row["status"] = "active"
                row["refresh_token"] = tokens.get("refresh_token", "")
                row["access_token"] = tokens.get("access_token", "")
                row["updated_at"] = utcnow()
                return cast("dict[str, object]", row)
        grant_id = new_id()
        row = {
            "id": grant_id,
            "tenant_id": saved["tenant_id"],
            "user_id": saved["user_id"],
            "provider_id": provider["id"],
            "scopes": as_sequence(provider.get("default_scopes")),
            "status": "active",
            "refresh_token": tokens.get("refresh_token", ""),
            "access_token": tokens.get("access_token", ""),
            "external_account_label": "",
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        self.store.credential_grants[grant_id] = row
        return row

    def _provider(self, actor: Actor, provider_id: uuid.UUID) -> dict[str, object]:
        row = self.store.credential_providers.get(provider_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _provider_view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "slug": row["slug"],
            "name": row["name"],
            "kind": row["kind"],
            "authorize_url": row.get("authorize_url"),
            "token_url": row.get("token_url"),
            "client_id": row.get("client_id"),
            "default_scopes": row.get("default_scopes") or [],
            "status": row.get("status"),
        }

    def _grant_view(self, row: dict[str, object]) -> dict[str, object]:
        provider = self.store.credential_providers.get(row.get("provider_id"))
        slug = provider.get("slug") if isinstance(provider, dict) else ""
        return {
            "id": str(row["id"]),
            "provider_id": str(row["provider_id"]),
            "provider_slug": slug,
            "status": row.get("status"),
            "external_account_label": row.get("external_account_label") or "",
            "scopes": row.get("scopes") or [],
        }

    def _audit(self, actor: Actor, action: str, target_id: uuid.UUID) -> None:
        self.store.audit_log.append(
            {
                "tenant_id": str(actor.tenant_id),
                "actor_id": str(actor.user_id),
                "action": action,
                "target_type": "credential_provider",
                "target_id": str(target_id),
                "detail": {},
                "outcome": "success",
                "at": utcnow().isoformat(),
            }
        )


async def _post_token(url: str, form: dict[str, str], store: Any) -> dict[str, str]:
    transport = getattr(store, "oauth_transport", None)
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(url, data=form)
    if response.status_code >= 300:
        raise ArError(ErrorCode.BAD_REQUEST, "invalid_grant")
    body = response.json()
    if not isinstance(body, dict) or "access_token" not in body:
        raise ArError(ErrorCode.BAD_REQUEST, "invalid_grant")
    return {
        "access_token": str(body["access_token"]),
        "refresh_token": str(body.get("refresh_token") or ""),
    }


def _seal(value: str) -> bytes:
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(_KEY).encrypt(nonce, value.encode(), b"token")


def _open(blob: bytes) -> str:
    if len(blob) < 13:
        return ""
    try:
        return AESGCM(_KEY).decrypt(blob[:12], blob[12:], b"token").decode()
    except InvalidTag:
        return ""
