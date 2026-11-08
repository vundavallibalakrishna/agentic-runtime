"""Stored, per-connection browser sign-in. Task: M40-T05c.

A browser connection holds a site's session state (cookies and storage) sealed with the
connection key and scoped to the tenant and owner. The trusted runtime — never the model —
unseals it at claim time and injects it into a fresh, isolated container context over the
agent's ``/admin/session`` channel. The model only ever names the connection; the state
never reaches model context, a tool argument, a snapshot, a log, a trace or an error.
Spec: docs/03-specs/12-sandbox-manager.md §7; docs/06-security/audit.md §3.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import httpx
import orjson

from ar_common.errors import ConflictError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.offload import blocking
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.secrets.crypto import open_sealed, seal
from ar_domain.tools.service_connections import connection_key

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_STORAGE_LIMIT = 2 * 1024 * 1024


def _book(store: Any) -> dict[uuid.UUID, dict[str, object]]:
    book = getattr(store, "browser_connections", None)
    if book is None:
        store.browser_connections = {}
        book = store.browser_connections
    return cast("dict[uuid.UUID, dict[str, object]]", book)


def _view(row: dict[str, object]) -> dict[str, object]:
    """The public shape of a connection. It never carries the sealed state."""
    return {
        "id": str(row["id"]),
        "name": row.get("name"),
        "allowedOrigins": [str(o) for o in _as_list(row.get("allowed_origins"))],
        "status": row.get("status"),
        "version": row.get("version", 1),
        "expiresAt": row.get("expires_at"),
        "createdAt": row.get("created_at"),
        "lastUsedAt": row.get("last_used_at"),
    }


def _find(store: Any, actor: Actor, reference: str) -> dict[str, object] | None:
    """Resolve a connection the actor owns, by name or id. Another tenant's is invisible."""
    ref = str(reference or "").strip()
    for row in _book(store).values():
        if row.get("tenant_id") != actor.tenant_id or row.get("owner_user_id") != actor.user_id:
            continue
        if ref and (str(row.get("name")).lower() == ref.lower() or str(row.get("id")) == ref):
            return row
    return None


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _expired(row: dict[str, object]) -> bool:
    """True when the connection carries an ISO expiry that is now in the past."""
    raw = row.get("expires_at")
    if not raw:
        return False
    try:
        moment = datetime.fromisoformat(str(raw))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment <= utcnow()


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "is_error": True, "code": code}


def _audit(store: Any, row: dict[str, object], action: str, outcome: str, run: object) -> None:
    """Record a connection event. The detail never includes the session state."""
    remember(
        store,
        tenant_id=row.get("tenant_id"),
        actor_id=row.get("owner_user_id"),
        action=action,
        target_type="browser_connection",
        target_id=row.get("id"),
        detail={
            "name": row.get("name"),
            "outcome": outcome,
            "run_id": str(run) if run else "",
        },
    )


def _admin_post(
    sandbox: dict[str, object], path: str, payload: dict[str, object]
) -> dict[str, object]:
    """POST to the agent's trusted admin channel. The payload (session state) is never logged."""
    endpoint = str(sandbox.get("endpoint_url") or "").rstrip("/")
    token = str(sandbox.get("agent_token") or sandbox.get("token") or "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with httpx.Client(timeout=60.0) as client:
            response = blocking(
                client.post, f"{endpoint}/admin/{path}", json=payload, headers=headers
            )
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError:
        return {"status": "unreachable"}
    return body if isinstance(body, dict) else {"status": "unexpected"}


class BrowserConnectionBook:
    """The tenant's browser connections. Create, list and revoke; the state stays sealed."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def create(
        self,
        actor: Actor,
        *,
        name: str,
        origins: list[str],
        storage_state: bytes,
        expires_at: str | None = None,
    ) -> dict[str, object]:
        clean = str(name or "").strip()
        if not clean:
            raise ValidationFailedError("a connection name is required")
        if len(storage_state) > _STORAGE_LIMIT:
            raise ValidationFailedError("the session state is too large")
        for existing in _book(self.store).values():
            same = existing.get("tenant_id") == actor.tenant_id
            if (
                same
                and str(existing.get("name")).lower() == clean.lower()
                and existing.get("status") != "revoked"
            ):
                raise ConflictError("a browser connection with that name already exists")
        now = utcnow()
        connection_id = new_id()
        row: dict[str, object] = {
            "id": connection_id,
            "tenant_id": actor.tenant_id,
            "owner_user_id": actor.user_id,
            "name": clean,
            "allowed_origins": [str(origin) for origin in (origins or [])],
            "sealed": seal(connection_key(), storage_state),
            "status": "active",
            "version": 1,
            "expires_at": str(expires_at) if expires_at else None,
            "created_at": now,
            "updated_at": now,
            "last_used_at": None,
        }
        _book(self.store)[connection_id] = row
        _audit(self.store, row, "browser_connection.created", "ok", None)
        return _view(row)

    def list(self, actor: Actor) -> list[dict[str, object]]:
        return [
            _view(row)
            for row in _book(self.store).values()
            if row.get("tenant_id") == actor.tenant_id and row.get("owner_user_id") == actor.user_id
        ]

    def revoke(self, actor: Actor, reference: str) -> dict[str, object]:
        row = _find(self.store, actor, reference)
        if row is None:
            raise ValidationFailedError("no such browser connection")
        row["status"] = "revoked"
        row["updated_at"] = utcnow()
        _audit(self.store, row, "browser_connection.revoked", "ok", None)
        return _view(row)


def restore_into_context(  # noqa: PLR0911 - each security guard returns on its own
    store: Any, sandbox: dict[str, object], actor: Actor, reference: str
) -> dict[str, object]:
    """Inject a connection's sealed state into the container context, at claim time.

    Returns an opaque result for the model: the connection name, a handle and a status, and
    nothing of the session itself. Every refusal is audited; no refusal reveals the state.
    """
    if not bool(sandbox.get("endpoint_url")):
        return _error("browser_unavailable", "a signed-in browser needs a running computer")
    row = _find(store, actor, reference)
    if row is None:
        # Another tenant's connection, or a name that does not exist: indistinguishable.
        return _error("not_found", f"no browser connection named {reference} is available to you")
    status = str(row.get("status"))
    run = sandbox.get("run_id") or sandbox.get("_run_id")
    if status != "active":
        _audit(store, row, "browser_connection.denied", status, run)
        return _error("forbidden", f"browser connection {row.get('name')} is {status}")
    if _expired(row):
        row["status"] = "expired"
        row["updated_at"] = utcnow()
        _audit(store, row, "browser_connection.denied", "expired", run)
        return _error("forbidden", f"browser connection {row.get('name')} has expired")
    sealed = row.get("sealed")
    try:
        opened = open_sealed(connection_key(), sealed if isinstance(sealed, bytes) else b"")
        storage_state = orjson.loads(opened)
    except Exception:  # noqa: BLE001 - never surface why the sealed state failed to open
        _audit(store, row, "browser_connection.restored", "unseal_failed", run)
        return _error("internal_error", "the stored session could not be opened")
    handle = uuid.uuid4().hex
    body = _admin_post(sandbox, "session", {"storage_state": storage_state, "handle": handle})
    if body.get("status") != "ready":
        _audit(store, row, "browser_connection.restored", "restore_failed", run)
        return _error("sandbox_unavailable", "the computer could not restore the session")
    row["last_used_at"] = utcnow()
    # Track which connection and version this sandbox restored, so a later save writes back
    # to the same connection and a stale write (another run advanced it) is refused.
    sandbox["browser_connection_id"] = row["id"]
    sandbox["browser_connection_version"] = row.get("version", 1)
    _audit(store, row, "browser_connection.restored", "ok", run)
    return {
        "text": f"signed in with the {row.get('name')} connection",
        "structured": {
            "connection": row.get("name"),
            "handle": handle,
            "status": "authenticated",
        },
        "is_error": False,
    }


def save_session(store: Any, sandbox: dict[str, object], actor: Actor) -> dict[str, object]:
    """Capture the container's current session state and re-seal it to its connection.

    Only the connection this sandbox restored can be written, and only if no other run has
    advanced it since (optimistic version check). The captured state is re-sealed by the
    trusted runtime and never returned to or seen by the model.
    """
    connection_id = sandbox.get("browser_connection_id")
    if not isinstance(connection_id, uuid.UUID):
        return _error("validation_failed", "sign in with a connection before saving the session")
    row = _book(store).get(connection_id)
    run = sandbox.get("run_id") or sandbox.get("_run_id")
    if (
        row is None
        or row.get("tenant_id") != actor.tenant_id
        or row.get("owner_user_id") != actor.user_id
        or row.get("status") != "active"
    ):
        return _error("forbidden", "the connection is no longer available to save to")
    if row.get("version") != sandbox.get("browser_connection_version"):
        _audit(store, row, "browser_connection.updated", "stale", run)
        return _error("conflict", "the connection changed since sign-in; sign in again to save")
    body = _admin_post(sandbox, "session/export", {})
    state = body.get("storage_state")
    if body.get("status") != "ready" or not isinstance(state, dict):
        return _error("sandbox_unavailable", "the computer had no session to save")
    current = row.get("version")
    row["sealed"] = seal(connection_key(), orjson.dumps(state))
    row["version"] = (current if isinstance(current, int) else 1) + 1
    row["updated_at"] = utcnow()
    sandbox["browser_connection_version"] = row["version"]
    _audit(store, row, "browser_connection.updated", "ok", run)
    return {
        "text": f"saved the session to the {row.get('name')} connection",
        "structured": {"connection": row.get("name"), "version": row["version"], "status": "saved"},
        "is_error": False,
    }
