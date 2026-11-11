"""Stage 14: a failed write cannot poison the process, and hashes stay idempotent."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from ar_domain.conversations.tables import Run
from ar_domain.conversations.triggers import trigger_check_sql
from ar_domain.durable.flush import flush_store
from ar_domain.durable.m24 import save_library_documents
from ar_domain.durable.tracking import install_tracking
from ar_domain.models.urls import chat_completions_url
from ar_testing.demo import demo_application


def test_run_trigger_check_includes_research_from_one_list() -> None:
    text = next(
        str(constraint.sqltext)
        for constraint in Run.__table__.constraints
        if "trigger IN" in str(getattr(constraint, "sqltext", ""))
    )
    assert text.replace(" ", "") == trigger_check_sql().replace(" ", "")
    assert "'research'" in text


def test_chat_completions_url_keeps_the_provider_prefix() -> None:
    assert (
        chat_completions_url("https://api.deepinfra.com/v1/openai")
        == "https://api.deepinfra.com/v1/openai/chat/completions"
    )
    assert (
        chat_completions_url("https://api.deepinfra.com/v1/openai/chat/completions")
        == "https://api.deepinfra.com/v1/openai/chat/completions"
    )


def test_a_failed_flush_is_discarded_before_the_next_login() -> None:
    app = demo_application()
    store = app.state.chat
    install_tracking(store)

    class _Begin:
        async def __aenter__(self) -> _Begin:
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

    class _Session:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def begin(self) -> _Begin:
            return _Begin()

        async def execute(self, statement: object, _params: object = None) -> SimpleNamespace:
            if "INSERT INTO runs" in str(statement):
                raise IntegrityError("INSERT", {}, Exception("ck_runs_trigger"))

            def _first() -> None:
                return None

            return SimpleNamespace(first=_first)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("ar_domain.durable.flush.AsyncSession", _Session)
    from sqlalchemy.ext.asyncio import create_async_engine

    store.durable_engine = create_async_engine("postgresql+asyncpg://ar:ar@127.0.0.1:1/none")
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "agent_version_id": version_id,
        "user_id": user_id,
        "conversation_id": uuid.uuid4(),
        "trigger": "not-a-real-trigger",
        "status": "queued",
        "depth": 0,
    }
    try:
        with pytest.raises(IntegrityError):
            asyncio.run(flush_store(store))
        assert run_id not in store.runs
        bucket = store.runs
        assert run_id not in getattr(bucket, "dirty", set())
        store.durable_engine = None
        from fastapi.testclient import TestClient

        answer = TestClient(app).post(
            "/api/v1/auth/login",
            json={"email": "admin@dev.local", "password": "dev-password"},
        )
        assert answer.status_code == 200
    finally:
        monkeypatch.undo()


class _Result:
    def __init__(self, row: object) -> None:
        self._row = row

    def first(self) -> object:
        return self._row


class _HashSession:
    def __init__(self) -> None:
        self.inserted = 0

    async def execute(self, statement: object, params: object = None) -> _Result:
        sql = str(statement)
        if "SELECT id FROM library_documents" in sql:
            return _Result((uuid.UUID("11111111-1111-4111-8111-111111111111"),))
        if sql.strip().upper().startswith("INSERT"):
            self.inserted += 1
        return _Result(None)


def test_library_writer_adopts_an_existing_hash() -> None:
    session = _HashSession()
    new_id = uuid.uuid4()
    adopted = asyncio.run(
        save_library_documents(
            session,  # type: ignore[arg-type]
            [
                {
                    "id": new_id,
                    "tenant_id": uuid.uuid4(),
                    "owner_user_id": uuid.uuid4(),
                    "content_hash": "abc",
                    "title": "Again",
                }
            ],
        )
    )
    assert session.inserted == 0
    assert adopted[new_id] == uuid.UUID("11111111-1111-4111-8111-111111111111")
