"""M35: durable bytes, cache eviction, job progress, A2A list and push."""

import asyncio
import io
import uuid
from types import SimpleNamespace

import httpx
import pytest
from pypdf import PdfWriter

from ar_common.errors import NotFoundError
from ar_domain.chat.eviction import evict_chat_cache, recall_conversation
from ar_domain.chat.service import demo_id
from ar_domain.documents.extract import ExtractError, extract_bytes
from ar_domain.durability.store import clear_workspace_dir, read_blob
from ar_domain.durability.tables import A2APushConfig, FileBlobPayload, JobProgress, WorkspaceFile
from ar_domain.exposure import a2a, keys
from ar_domain.jobs.progress import jobs_for, mark_jobs_interrupted, note_job
from ar_domain.routines.clock import build_schedule, schedule_workflow_id
from ar_domain.tools.general import dispatch_general
from ar_testing.demo import demo_store


def test_tables_match_the_migration_names() -> None:
    assert FileBlobPayload.__tablename__ == "file_blob_payloads"
    assert WorkspaceFile.__tablename__ == "workspace_files"
    assert JobProgress.__tablename__ == "job_progress"
    assert A2APushConfig.__tablename__ == "a2a_push_configs"


def test_file_bytes_survive_when_the_process_cache_drops_them() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    uploaded = store.upload(tenant, user, "note.txt", "text/plain", b"hello durable")
    file_id = uuid.UUID(str(uploaded["id"]))
    store.blobs.pop(file_id)
    assert read_blob(store, file_id) == b"hello durable"
    data, mime = store.file_bytes(tenant, user, file_id)
    assert data == b"hello durable"
    assert mime == "text/plain"
    store.delete_file(tenant, user, file_id)
    assert read_blob(store, file_id) is None


def test_workspace_bytes_restore_after_the_temp_dir_is_gone() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    run_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "status": "running",
    }
    arguments = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_run_id": run_id,
        "_conversation_id": conversation_id,
        "path": "/workspace/outputs/note.txt",
        "content": "kept across restart",
    }
    written = dispatch_general(store, "write_file", arguments)
    assert written["is_error"] is False
    assert store.workspace_files
    clear_workspace_dir(run_id)
    read = dispatch_general(
        store,
        "read_file",
        {**arguments, "path": "/workspace/outputs/note.txt"},
    )
    assert read["is_error"] is False
    assert "kept across restart" in str(read["text"])


def test_a_new_run_can_see_files_from_an_interrupted_run() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation_id = uuid.uuid4()
    first = uuid.uuid4()
    second = uuid.uuid4()
    store.runs[first] = {
        "id": first,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "status": "failed",
        "error": {"code": "interrupted"},
        "ended_at": "1",
    }
    store.runs[second] = {
        "id": second,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "status": "running",
    }
    base = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_conversation_id": conversation_id,
    }
    written = dispatch_general(
        store,
        "write_file",
        {**base, "_run_id": first, "path": "/workspace/outputs/note.txt", "content": "resume me"},
    )
    assert written["is_error"] is False
    clear_workspace_dir(first)
    clear_workspace_dir(second)
    read = dispatch_general(
        store,
        "read_file",
        {**base, "_run_id": second, "path": "/workspace/outputs/note.txt"},
    )
    assert read["is_error"] is False
    assert "resume me" in str(read["text"])
    restored = jobs_for(store, conversation_id)
    assert any(row["kind"] == "workspace" for row in restored)


def test_chat_cache_drops_old_messages_and_reloads_them() -> None:
    store = demo_store()
    store.cache_limits = {"messages": 1, "runs": 10, "events": 10, "blobs_bytes": 10_000}
    tenant = demo_id("tenant")
    user = demo_id("admin")
    old = uuid.uuid4()
    new = uuid.uuid4()
    message_id = uuid.uuid4()
    store.conversations[old] = _conversation(old, tenant, user, "Old")
    store.conversations[new] = _conversation(new, tenant, user, "New")
    store.messages[message_id] = {
        "id": message_id,
        "tenant_id": tenant,
        "conversation_id": old,
        "text": "earlier",
        "content": [{"type": "text", "text": "earlier"}],
    }
    kept = uuid.uuid4()
    store.messages[kept] = {
        "id": kept,
        "tenant_id": tenant,
        "conversation_id": new,
        "text": "later",
        "content": [{"type": "text", "text": "later"}],
    }
    removed = evict_chat_cache(store)
    assert removed["messages"] >= 1
    assert message_id not in store.messages
    assert kept in store.messages
    assert old in store.conversations
    assert old in store.evicted_conversations

    class _Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def mappings(self) -> list[dict[str, object]]:
            return self._rows

    class _Connection:
        def execute(self, sql: object, params: dict[str, object]) -> _Result:
            if "messages" in str(sql):
                return _Result(
                    [
                        {
                            "id": message_id,
                            "tenant_id": tenant,
                            "conversation_id": old,
                            "content": [{"type": "text", "text": "earlier"}],
                            "created_at": "2026-11-05T00:00:00+00:00",
                            "is_active_branch": True,
                        }
                    ]
                )
            return _Result([])

        def __enter__(self) -> _Connection:
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

    store.durable_engine = SimpleNamespace(sync_engine=SimpleNamespace(connect=_Connection))
    assert recall_conversation(store, old) is True
    body = store.get_conversation(tenant, user, old, read_all=False)
    messages = body["messages"]
    assert isinstance(messages, list)
    texts = [str(item.get("text") or "") for item in messages if isinstance(item, dict)]
    assert "earlier" in texts


def test_active_runs_are_not_evicted() -> None:
    store = demo_store()
    store.cache_limits = {"messages": 0, "runs": 0, "events": 0, "blobs_bytes": 0}
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation_id = uuid.uuid4()
    run_id = uuid.uuid4()
    message_id = uuid.uuid4()
    store.conversations[conversation_id] = _conversation(conversation_id, tenant, user, "Live")
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "status": "running",
    }
    store.messages[message_id] = {
        "id": message_id,
        "conversation_id": conversation_id,
        "tenant_id": tenant,
        "text": "working",
    }
    store.events[run_id] = [{"type": "run.queued"}]
    evict_chat_cache(store)
    assert message_id in store.messages
    assert run_id in store.runs
    assert run_id in store.events


def test_pdf_pages_report_progress_and_a_restart_interrupts_the_job() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    run_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    arguments = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_run_id": run_id,
        "_conversation_id": conversation_id,
    }
    seen: list[tuple[int, int]] = []
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ExtractError):
        extract_bytes(
            buffer.getvalue(),
            filename="blank.pdf",
            on_page=lambda done, total: seen.append((done, total)),
        )
    assert seen == [(1, 2), (2, 2)]
    note_job(
        store,
        arguments,
        kind="ocr",
        tool_name="documents.ocr",
        label="blank.pdf",
        completed=1,
        total=2,
        status="running",
    )
    assert mark_jobs_interrupted(store)
    jobs = jobs_for(store, conversation_id)
    assert jobs[0]["status"] == "interrupted"
    assert jobs[0]["completed"] == 1
    assert jobs[0]["total"] == 2
    actions = [row["action"] for row in store.audit_log]
    assert "job.progressed" in actions


def test_schedule_workflow_id_is_per_fire() -> None:
    routine_id = uuid.uuid4()
    workflow_id = schedule_workflow_id(routine_id)
    assert "{{.ScheduledTime.Unix}}" in workflow_id
    assert str(routine_id) in workflow_id
    schedule = build_schedule(
        {
            "id": routine_id,
            "status": "active",
            "concurrency_policy": "skip",
            "trigger_config": {"cron": "*/5 * * * *", "timezone": "UTC", "jitter_s": 0},
        }
    )
    assert schedule.spec.cron_expressions == ["*/5 * * * *"]
    assert schedule.action.id == workflow_id
    assert schedule.action.args[0]["source"] == "schedule"


def test_a2a_lists_tasks_and_stores_a_push_config() -> None:
    store = demo_store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        run = store.runs[run_id]
        run["status"] = "completed"
        assistant = store.messages[run["assistant_message_id"]]
        assistant["text"] = "6"
        assistant["status"] = "completed"

    store.generate = generate  # type: ignore[method-assign]
    row, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="A2A",
        monthly_quota=5,
    )
    other, _other_secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Other",
        monthly_quota=5,
    )
    sent = [
        asyncio.run(
            a2a.send_task(
                store,
                row,
                "assistant",
                {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
            )
        )
        for text in ("one", "two", "three")
    ]
    first = asyncio.run(
        a2a.rpc(
            store,
            row,
            "assistant",
            {"jsonrpc": "2.0", "id": 1, "method": "tasks/list", "params": {"page_size": 2}},
        )
    )
    assert len(first["result"]["tasks"]) == 2
    token = first["result"]["next_page_token"]
    assert token
    second = asyncio.run(
        a2a.rpc(
            store,
            row,
            "assistant",
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tasks/list",
                "params": {"page_size": 2, "page_token": token},
            },
        )
    )
    assert len(second["result"]["tasks"]) == 1
    assert second["result"]["next_page_token"] == ""
    hidden = asyncio.run(
        a2a.rpc(
            store,
            other,
            "assistant",
            {"jsonrpc": "2.0", "id": 3, "method": "tasks/list", "params": {}},
        )
    )
    assert hidden["result"]["tasks"] == []
    seen: dict[str, str] = {}

    def http_send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url
        headers = kwargs.get("headers")
        if isinstance(headers, dict):
            seen["authorization"] = str(headers.get("authorization") or "")
        return httpx.Response(204)

    store.http_send = http_send  # type: ignore[attr-defined]
    task_id = sent[0]["id"]
    configured = asyncio.run(
        a2a.rpc(
            store,
            row,
            "assistant",
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tasks/pushNotificationConfig/set",
                "params": {
                    "task_id": task_id,
                    "push_notification_config": {
                        "url": "http://127.0.0.1:9/hook",
                        "token": "echo-token",
                    },
                },
            },
        )
    )
    assert configured["result"]["push_notification_config"]["token"] == "echo-token"  # noqa: S105
    fetched = asyncio.run(
        a2a.rpc(
            store,
            row,
            "assistant",
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tasks/pushNotificationConfig/get",
                "params": {"task_id": task_id, "id": "default"},
            },
        )
    )
    assert fetched["result"]["push_notification_config"]["url"] == "http://127.0.0.1:9/hook"
    with pytest.raises(NotFoundError):
        a2a.get_push_config(store, other, {"task_id": task_id, "id": "default"})
    a2a.cancel_task(store, row, "assistant", uuid.UUID(task_id))
    assert seen["authorization"] == "Bearer echo-token"
    removed = asyncio.run(
        a2a.rpc(
            store,
            row,
            "assistant",
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tasks/pushNotificationConfig/delete",
                "params": {"task_id": task_id},
            },
        )
    )
    assert removed["result"]["task_id"] == task_id
    missing = asyncio.run(
        a2a.rpc(store, row, "assistant", {"jsonrpc": "2.0", "id": 7, "method": "tasks/resubscribe"})
    )
    assert missing["error"]["code"] == -32000
    actions = [item["action"] for item in store.audit_log]
    assert "a2a_push.configured" in actions
    assert "a2a_push.removed" in actions


def _conversation(
    conversation_id: uuid.UUID, tenant: uuid.UUID, user: uuid.UUID, title: str
) -> dict[str, object]:
    return {
        "id": conversation_id,
        "tenant_id": tenant,
        "user_id": user,
        "title": title,
        "deleted_at": None,
        "active_run_id": None,
        "is_preview": False,
        "updated_at": title,
    }
