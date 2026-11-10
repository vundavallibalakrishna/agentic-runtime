"""Encrypted server-side sessions. Spec: docs/03-specs/01-api-bff.md §3."""

import base64
import binascii
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import orjson

from ar_common.time import utcnow
from ar_domain.secrets.crypto import open_sealed, seal


@dataclass(slots=True)
class SessionData:
    """Values stored at ``ar:sess:{id}``."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    csrf_token: str
    created_at: datetime
    last_seen_at: datetime
    step_up_at: datetime | None = None
    access_token: str = ""
    refresh_token: str = ""
    email: str = ""
    display_name: str = ""
    roles: list[str] | None = None
    permissions: list[str] | None = None
    amr: list[str] | None = None
    widget_integration_id: uuid.UUID | None = None
    widget_conversation_id: uuid.UUID | None = None

    def to_json(self) -> bytes:
        return orjson.dumps(
            {
                "tenant_id": str(self.tenant_id),
                "user_id": str(self.user_id),
                "csrf_token": self.csrf_token,
                "created_at": self.created_at.isoformat(),
                "last_seen_at": self.last_seen_at.isoformat(),
                "step_up_at": None if self.step_up_at is None else self.step_up_at.isoformat(),
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "email": self.email,
                "display_name": self.display_name,
                "roles": list(self.roles or []),
                "permissions": list(self.permissions or []),
                "amr": list(self.amr or []),
                "widget_integration_id": str(self.widget_integration_id)
                if self.widget_integration_id
                else None,
                "widget_conversation_id": str(self.widget_conversation_id)
                if self.widget_conversation_id
                else None,
            }
        )

    @classmethod
    def from_json(cls, raw: bytes) -> SessionData:
        payload = orjson.loads(raw)
        step = payload.get("step_up_at")
        return cls(
            tenant_id=uuid.UUID(payload["tenant_id"]),
            user_id=uuid.UUID(payload["user_id"]),
            csrf_token=str(payload["csrf_token"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            last_seen_at=datetime.fromisoformat(payload["last_seen_at"]),
            step_up_at=None if step is None else datetime.fromisoformat(step),
            access_token=str(payload.get("access_token", "")),
            refresh_token=str(payload.get("refresh_token", "")),
            email=str(payload.get("email", "")),
            display_name=str(payload.get("display_name", "")),
            roles=_strings(payload.get("roles")),
            permissions=_strings(payload.get("permissions")),
            amr=_strings(payload.get("amr")),
            widget_integration_id=uuid.UUID(payload["widget_integration_id"])
            if payload.get("widget_integration_id")
            else None,
            widget_conversation_id=uuid.UUID(payload["widget_conversation_id"])
            if payload.get("widget_conversation_id")
            else None,
        )


class MemorySessionStore:
    """In-process session map. Production swaps in Valkey."""

    def __init__(self, key: bytes) -> None:
        self.key = key
        self._values: dict[str, bytes] = {}
        self._expires: dict[str, datetime] = {}

    async def put(self, session_id: str, data: SessionData, ttl_s: int) -> None:
        self._expires[session_id] = utcnow() + timedelta(seconds=ttl_s)
        self._values[session_id] = seal(self.key, data.to_json())

    async def get(self, session_id: str) -> SessionData | None:
        expiry = self._expires.get(session_id)
        if expiry is None or expiry <= utcnow():
            await self.delete(session_id)
            return None
        blob = self._values.get(session_id)
        if blob is None:
            return None
        return SessionData.from_json(open_sealed(self.key, blob))

    async def update(self, session_id: str, data: SessionData) -> None:
        """Update session data without extending its original expiration."""
        if await self.get(session_id) is not None:
            self._values[session_id] = seal(self.key, data.to_json())

    async def delete(self, session_id: str) -> None:
        self._values.pop(session_id, None)
        self._expires.pop(session_id, None)


class ValkeySessionStore:
    """Encrypted session map in Valkey, shared by every API replica.

    The payload is the same sealed blob the memory store writes. A Valkey error
    is ``unavailable`` (the caller is not treated as signed out).
    """

    def __init__(self, key: bytes, url: str, *, client: object | None = None) -> None:
        self.key = key
        self.url = url
        self._redis = client

    async def put(self, session_id: str, data: SessionData, ttl_s: int) -> None:
        blob = base64.b64encode(seal(self.key, data.to_json())).decode("ascii")
        try:
            await self._client().set(  # type: ignore[attr-defined]
                self._name(session_id), blob, ex=max(1, ttl_s)
            )
        except Exception as exc:
            raise _unavailable() from exc

    async def get(self, session_id: str) -> SessionData | None:
        try:
            raw = await self._client().get(self._name(session_id))  # type: ignore[attr-defined]
        except Exception as exc:
            raise _unavailable() from exc
        if not isinstance(raw, str) or not raw:
            return None
        try:
            opened = open_sealed(self.key, base64.b64decode(raw))
            return SessionData.from_json(opened)
        except Exception:  # noqa: BLE001 - a corrupt blob is not a live session
            return None

    async def update(self, session_id: str, data: SessionData) -> None:
        """Replace the payload and keep the remaining lifetime."""
        name = self._name(session_id)
        try:
            ttl = int(await self._client().ttl(name))  # type: ignore[attr-defined]
        except Exception as exc:
            raise _unavailable() from exc
        if ttl < 1:
            return
        await self.put(session_id, data, ttl)

    async def delete(self, session_id: str) -> None:
        try:
            await self._client().delete(self._name(session_id))  # type: ignore[attr-defined]
        except Exception as exc:
            raise _unavailable() from exc

    def _client(self) -> object:
        if self._redis is None:
            from ar_common.valkey import valkey_client  # noqa: PLC0415

            self._redis = valkey_client(self.url, socket_connect_timeout=1, socket_timeout=1)
        return self._redis

    @staticmethod
    def _name(session_id: str) -> str:
        return f"ar:sess:{session_id}"


def _unavailable() -> Exception:
    from ar_common.errors import UnavailableError  # noqa: PLC0415

    return UnavailableError("session store is unavailable")


def session_key_bytes(raw_b64: str, fallback: str, *, prod: bool) -> bytes:
    """Decode ``AR_SESSION_ENCRYPTION_KEY`` or derive a dev key.

    A placeholder such as ``install-time`` is not a key. Outside production it
    falls through to the cursor-secret digest instead of crashing the process.
    """
    if raw_b64:
        padding = "=" * (-len(raw_b64) % 4)
        try:
            decoded = base64.b64decode(raw_b64 + padding)
        except ValueError, binascii.Error:
            decoded = b""
        if len(decoded) == 32:
            return decoded
    if prod:
        raise RuntimeError("AR_SESSION_ENCRYPTION_KEY must be 32 bytes, base64")
    return hashlib.sha256(fallback.encode()).digest()


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def remember_profile(
    data: SessionData,
    *,
    email: str,
    display_name: str,
    roles: list[str] | tuple[str, ...],
    permissions: list[str] | frozenset[str],
) -> None:
    """Copy the signed-in person onto the session. The loader does not guess."""
    data.email = email
    data.display_name = display_name
    data.roles = list(roles)
    data.permissions = list(permissions)


def new_session(tenant_id: uuid.UUID, user_id: uuid.UUID) -> tuple[str, SessionData]:
    """Create a session id and its payload."""
    session_id = str(uuid.uuid4())
    now = utcnow()
    data = SessionData(
        tenant_id=tenant_id,
        user_id=user_id,
        csrf_token=uuid.uuid4().hex,
        created_at=now,
        last_seen_at=now,
    )
    return session_id, data
