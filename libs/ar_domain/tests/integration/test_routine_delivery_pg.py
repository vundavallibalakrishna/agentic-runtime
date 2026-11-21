"""A held delivery survives the process that asked for it, and is sent by another.

The event's delivery results, the approval and its tool call are read back from the
database by a second store, which sends the approved delivery; a third reads the result.
"""

import os
import subprocess
import threading
import uuid
from socketserver import StreamRequestHandler, ThreadingTCPServer

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.settings import get_settings, set_settings
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.engine import (
    accept_routine_event,
    complete_routine_event,
    prepare_routine_run,
    release_delivery,
)

pytestmark = pytest.mark.integration


class _Mail(StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"220 ready\r\n")
        lines: list[str] | None = None
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").rstrip("\r\n")
            if lines is not None:
                if line == ".":
                    self.server.messages.append("\n".join(lines))  # type: ignore[attr-defined]
                    lines = None
                    self.wfile.write(b"250 ok\r\n")
                else:
                    lines.append(line)
            elif line.upper().startswith("DATA"):
                lines = []
                self.wfile.write(b"354 go\r\n")
            elif line.upper().startswith("QUIT"):
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


def _async_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


@pytest.fixture
def mail() -> object:
    server = ThreadingTCPServer(("127.0.0.1", 0), _Mail)
    server.messages = []  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = get_settings()
    set_settings(
        before.model_copy(
            update={
                "smtp_host": "127.0.0.1",
                "smtp_port": server.server_address[1],
                "egress_allow_loopback": True,
            }
        )
    )
    yield server
    set_settings(before)
    server.shutdown()
    server.server_close()


async def _bound(database_url: str) -> ChatService:
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    return store


async def test_a_held_delivery_is_read_back_and_sent_by_another_process(
    database_url: str, mail: ThreadingTCPServer
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    first = await _bound(database_url)
    tenant = first.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(first.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")
    slug = f"mailed-{uuid.uuid4().hex[:8]}"
    agent = first.ensure_assistant(tenant, admin)
    made = RoutineBook(first).create(
        actor,
        {
            "name": f"mail {slug}",
            "agent_id": uuid.UUID(str(agent["id"])),
            "instructions": "Say hello.",
            "trigger": {"type": "manual"},
            "delivery": [{"type": "email", "channel": "lead@customer.test"}],
        },
    )
    routine_id = uuid.UUID(str(made["id"]))
    accepted = accept_routine_event(
        first,
        routine_id=routine_id,
        source="manual",
        idempotency_key=slug,
        envelope={"type": "manual"},
    )
    event_id = uuid.UUID(str(accepted["event_id"]))
    prepared = prepare_routine_run(first, routine_id, event_id)
    run_id = uuid.UUID(str(prepared["run_id"]))
    first.runs[run_id]["status"] = "completed"
    first.runs[run_id]["result_summary"] = "Hello from the routine."
    done = complete_routine_event(first, event_id)
    assert done["status"] == "waiting"
    approval_id = uuid.UUID(str(done["deliveries"][0]["approval_id"]))  # type: ignore[index]
    await flush_store(first)
    conversation_id = first.runs[run_id]["conversation_id"]
    try:
        second = await _bound(database_url)
        held = second.routine_events[event_id]["detail"]["deliveries"]  # type: ignore[index]
        assert held == [{"target": "email", "result": "waiting", "approval_id": str(approval_id)}]
        approval = second.approvals[approval_id]
        assert approval["qualified_name"] == "delivery.email_send"
        assert second.tool_calls[approval["tool_call_id"]]["status"] == "awaiting_approval"
        approval["status"] = "approved"
        approval["decided_at"] = utcnow()
        sent = release_delivery(second, approval_id)
        assert sent["result"] == "posted"
        await flush_store(second)
        [message] = mail.messages  # type: ignore[attr-defined]
        assert "Hello from the routine." in message

        third = await _bound(database_url)
        shown = third.routine_events[event_id]["detail"]["deliveries"]  # type: ignore[index]
        assert [item["result"] for item in shown] == ["posted"]
        assert third.approvals[approval_id]["consumed_at"] is not None
        assert release_delivery(third, approval_id) == {"result": "posted", "duplicate": True}
        posts = [
            row
            for row in third.channel_posts.values()
            if str(row.get("id")) == str(sent["post_id"])
        ]
        assert posts and posts[0]["status"] == "posted"
        assert str(posts[0]["external_message_id"]) in message
        assert len(mail.messages) == 1  # type: ignore[attr-defined]
    finally:
        # The database is shared with the other tests of this run: leave it as it was found.
        async with AsyncSession(engine) as session, session.begin():
            for statement in (
                "DELETE FROM channel_posts WHERE detail->>'routine_id' = :routine_text",
                "UPDATE tool_calls SET approval_id = NULL WHERE run_id = :run",
                "DELETE FROM approvals WHERE run_id = :run",
                "DELETE FROM tool_calls WHERE run_id = :run",
                "DELETE FROM routines WHERE id = :routine",
                "DELETE FROM conversations WHERE id = :conversation",
            ):
                await session.execute(
                    text(statement),
                    {
                        "routine": routine_id,
                        "routine_text": str(routine_id),
                        "run": run_id,
                        "conversation": conversation_id,
                    },
                )
        await engine.dispose()
