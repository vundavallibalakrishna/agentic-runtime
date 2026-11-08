"""Security of stored browser sign-in. Task: M40-T05c.

The session state never reaches the model, and no one reaches another tenant's connection.
These are the mandatory isolation and non-disclosure tests; the real container restore is a
docker-gated canary. The trusted admin channel is replaced here so no Chromium is needed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson

from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.sandboxes import browser_auth
from ar_domain.sandboxes.browser_auth import (
    BrowserConnectionBook,
    restore_into_context,
    save_session,
)
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from typing import Any

    import pytest

_SECRET = "SUPER-SECRET-SESSION-TOKEN-7f3a"  # noqa: S105 - a test fixture, not a credential
_STATE = orjson.dumps(
    {"cookies": [{"name": "sid", "value": _SECRET, "domain": "example.com", "path": "/"}]}
)


def _actor(tenant: uuid.UUID, user: uuid.UUID) -> Actor:
    return Actor(tenant, user, PERMISSION_KEYS)


def _sandbox(tenant: uuid.UUID, user: uuid.UUID) -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "user_id": user,
        "endpoint_url": "http://127.0.0.1:65535",
        "agent_token": "t",
        "run_id": uuid.uuid4(),
    }


def _ready_channel(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Capture what the trusted channel receives and report a successful restore."""
    seen: list[dict[str, object]] = []

    def fake(sandbox: dict, path: str, payload: dict) -> dict:
        seen.append({"path": path, "payload": payload})
        return {"status": "ready", "handle": payload.get("handle")}

    monkeypatch.setattr(browser_auth, "_admin_post", fake)
    return seen


def _make(store: Any, actor: Actor, name: str = "acme") -> None:
    BrowserConnectionBook(store).create(
        actor, name=name, origins=["https://example.com"], storage_state=_STATE
    )


def test_the_state_reaches_the_trusted_channel_but_never_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = _actor(tenant, user)
    _make(store, actor)
    seen = _ready_channel(monkeypatch)
    result = restore_into_context(store, _sandbox(tenant, user), actor, "acme")
    # The model sees only an opaque result: connection name, a handle, a status.
    assert result["is_error"] is False
    assert result["structured"]["connection"] == "acme"
    assert result["structured"]["status"] == "authenticated"
    assert _SECRET not in orjson.dumps(result).decode()
    # The session state did travel the trusted admin channel.
    assert seen and seen[0]["path"] == "session"
    assert _SECRET in orjson.dumps(seen[0]["payload"]).decode()


def test_a_connection_view_never_carries_the_state() -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    view = BrowserConnectionBook(store).create(
        _actor(tenant, user), name="acme", origins=[], storage_state=_STATE
    )
    assert _SECRET not in orjson.dumps(view).decode()
    assert "sealed" not in view


def test_another_tenant_cannot_use_the_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    owner_tenant, owner = uuid.uuid4(), uuid.uuid4()
    _make(store, _actor(owner_tenant, owner))
    seen = _ready_channel(monkeypatch)
    # A different tenant names the same connection: it is simply not found.
    other = _actor(uuid.uuid4(), uuid.uuid4())
    result = restore_into_context(store, _sandbox(other.tenant_id, other.user_id), other, "acme")
    assert result["is_error"] is True
    assert result["code"] == "not_found"
    assert seen == [], "no state was unsealed or sent for another tenant"


def test_a_spoofed_connection_name_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    seen = _ready_channel(monkeypatch)
    result = restore_into_context(store, _sandbox(tenant, user), _actor(tenant, user), "../etc")
    assert result["is_error"] is True
    assert result["code"] == "not_found"
    assert seen == []


def test_a_revoked_connection_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = _actor(tenant, user)
    book = BrowserConnectionBook(store)
    book.create(actor, name="acme", origins=[], storage_state=_STATE)
    book.revoke(actor, "acme")
    seen = _ready_channel(monkeypatch)
    result = restore_into_context(store, _sandbox(tenant, user), actor, "acme")
    assert result["is_error"] is True
    assert result["code"] == "forbidden"
    assert seen == []


def test_sign_in_needs_a_running_container() -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = _actor(tenant, user)
    _make(store, actor)
    sandbox = _sandbox(tenant, user)
    del sandbox["endpoint_url"]  # no container
    result = restore_into_context(store, sandbox, actor, "acme")
    assert result["is_error"] is True
    assert result["code"] == "browser_unavailable"


def test_the_restore_is_audited_without_the_state(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = _actor(tenant, user)
    _make(store, actor)
    _ready_channel(monkeypatch)
    restore_into_context(store, _sandbox(tenant, user), actor, "acme")
    rows = [
        row for row in store.audit_log if str(row.get("action")) == "browser_connection.restored"
    ]
    assert rows, "the restore was not audited"
    assert _SECRET not in orjson.dumps(rows[-1].get("detail")).decode()
    assert rows[-1]["detail"]["outcome"] == "ok"


def test_an_expired_connection_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = _actor(tenant, user)
    BrowserConnectionBook(store).create(
        actor,
        name="acme",
        origins=[],
        storage_state=_STATE,
        expires_at="2000-01-01T00:00:00+00:00",
    )
    seen = _ready_channel(monkeypatch)
    result = restore_into_context(store, _sandbox(tenant, user), actor, "acme")
    assert result["is_error"] is True
    assert result["code"] == "forbidden"
    assert seen == [], "an expired connection is never unsealed or sent"


def _signed_in(monkeypatch: pytest.MonkeyPatch, captured: str) -> tuple:
    """Restore returns ready; export returns a fresh state. Gives (store, actor, sandbox)."""
    fresh = orjson.dumps({"cookies": [{"name": "sid", "value": captured}]})

    def fake(sandbox: dict, path: str, payload: dict) -> dict:
        if path == "session/export":
            return {"status": "ready", "storage_state": orjson.loads(fresh)}
        return {"status": "ready", "handle": payload.get("handle")}

    monkeypatch.setattr(browser_auth, "_admin_post", fake)
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = _actor(tenant, user)
    _make(store, actor)
    sandbox = _sandbox(tenant, user)
    restore_into_context(store, sandbox, actor, "acme")
    return store, actor, sandbox


def test_save_session_reseals_the_state_and_bumps_the_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, actor, sandbox = _signed_in(monkeypatch, "FRESH-CAPTURED-TOKEN")
    result = save_session(store, sandbox, actor)
    assert result["is_error"] is False
    assert result["structured"]["version"] == 2
    # The captured state never reaches the model result.
    assert "FRESH-CAPTURED-TOKEN" not in orjson.dumps(result).decode()
    # It was re-sealed to the connection (the row changed), still never in plaintext.
    row = next(iter(store.browser_connections.values()))
    assert row["version"] == 2
    assert b"FRESH-CAPTURED-TOKEN" not in bytes(row["sealed"])


def test_a_stale_save_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    store, actor, sandbox = _signed_in(monkeypatch, "X")
    # Another run advances the connection's version after this sandbox signed in.
    row = next(iter(store.browser_connections.values()))
    row["version"] = 5
    result = save_session(store, sandbox, actor)
    assert result["is_error"] is True
    assert result["code"] == "conflict"


def test_save_without_a_signin_is_refused() -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    result = save_session(store, _sandbox(tenant, user), _actor(tenant, user))
    assert result["is_error"] is True
    assert result["code"] == "validation_failed"
