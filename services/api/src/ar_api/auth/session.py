"""Encrypted server-side sessions. Spec: docs/03-specs/01-api-bff.md §3."""

import base64
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


def session_key_bytes(raw_b64: str, fallback: str, *, prod: bool) -> bytes:
    """Decode ``AR_SESSION_ENCRYPTION_KEY`` or derive a dev key."""
    if raw_b64:
        padding = "=" * (-len(raw_b64) % 4)
        decoded = base64.b64decode(raw_b64 + padding)
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
