"""Wire the stores that more than one API replica must share.

Dev and CI keep the process-local stores so a unit test does not need Valkey
or Postgres. Staging and production use Valkey for sessions and the run-event
bus, and the existing ``idempotency_keys`` table for idempotency.
"""

from __future__ import annotations

from fastapi import FastAPI

from ar_api.auth.session import MemorySessionStore, ValkeySessionStore
from ar_api.idempotency_store import PostgresIdempotencyStore
from ar_api.middleware.idempotency import MemoryIdempotencyStore
from ar_common.settings import BaseServiceSettings, uses_shared_process_state
from ar_domain.runs.event_bus import ValkeyRunBus


def install_process_state(app: FastAPI, settings: BaseServiceSettings, key: bytes) -> None:
    """Attach sessions, idempotency and the run-event bus for this environment."""
    if uses_shared_process_state(settings.env):
        app.state.sessions = ValkeySessionStore(key, settings.valkey_url)
        app.state.widget_sessions = ValkeySessionStore(key, settings.valkey_url)
        app.state.idempotency = PostgresIdempotencyStore(settings.database_url)
        app.state.chat.event_bus = ValkeyRunBus(settings.valkey_url)
    else:
        app.state.sessions = MemorySessionStore(key)
        app.state.widget_sessions = MemorySessionStore(key)
        app.state.idempotency = MemoryIdempotencyStore()
    app.state.chat.temporal_required = bool(settings.temporal_required)
