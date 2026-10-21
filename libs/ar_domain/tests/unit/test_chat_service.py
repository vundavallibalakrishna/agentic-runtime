"""Exercise the in-process chat store used by the API and the dev UI."""

import asyncio
import uuid

import pytest

from ar_common.errors import ArError, ConflictError, NotFoundError
from ar_domain.agents.logic import assistant_definition
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.files.logic import EICAR, MAX_UPLOAD_BYTES
from ar_ingest.workflows.file_process import process_upload, thumbnail_png
from ar_model_gateway.router import merge_params


def _ids() -> tuple[uuid.UUID, uuid.UUID]:
    return demo_id("tenant"), demo_id("admin")


@pytest.mark.asyncio
async def test_catalogue_agents_and_chat_ops() -> None:
    tenant, user = _ids()
    service = ChatService(allow_loopback=True, scanner="clamav")
    assert merge_params({"temperature": 0.2}, {"max_tokens": 8})["temperature"] == 0.2
    assert process_upload(b"hello", scanner="none")["scan_status"] == "skipped"
    assert thumbnail_png().startswith(b"\x89PNG")

    denied = pytest.raises(ArError)
    with denied:
        service.create_provider(tenant, "blocked", "fake", "http://10.1.1.1/v1", platform=False)
    with pytest.raises(ArError):
        service.create_provider(tenant, "odd", "nope", "http://127.0.0.1:8099/v1", platform=False)
    created = service.create_provider(
        tenant, "desk", "fake", "http://127.0.0.1:8099/v1", platform=False
    )
    provider_id = uuid.UUID(str(created["id"]))
    renamed = service.update_provider(tenant, provider_id, platform=False, name="desk-2")
    assert renamed["name"] == "desk-2"
    listed = service.list_providers(tenant)
    assert any(row["id"] == str(provider_id) for row in listed)
    probed = await service.test_provider(tenant, provider_id)
    assert "output" in probed
    model = service.create_model(
        tenant, provider_id, "desk-chat", "fake-chat", "chat", platform=False
    )
    model_id = uuid.UUID(str(model["id"]))
    assert service.list_models(tenant)
    with pytest.raises(ArError):
        service.create_alias(tenant, "Bad", "chat", model_id, platform=False)
    alias = service.create_alias(
        tenant, "desk", "chat", model_id, platform=False, fallback_model_ids=[model_id]
    )
    alias_id = uuid.UUID(str(alias["id"]))
    assert service.resolve(tenant, "reasoning") is not None
    tested = await service.test_alias(tenant, alias_id, [{"role": "user", "content": "ping"}])
    assert tested["output"]
    platform_id = next(
        item_id for item_id, row in service.providers.items() if row["tenant_id"] is None
    )
    with pytest.raises(ArError):
        service.update_provider(tenant, platform_id, platform=False, name="nope")

    agent = service.create_agent(tenant, user, "desk", "Desk")
    agent_id = uuid.UUID(str(agent["id"]))
    with pytest.raises(ConflictError):
        service.create_agent(tenant, user, "desk", "Again")
    definition = assistant_definition()
    definition["tools"] = [{"name": "search"}]
    service.save_draft(tenant, agent_id, definition)
    with pytest.raises(ArError):
        service.publish(tenant, agent_id, user)
    service.save_draft(tenant, agent_id, assistant_definition())
    published = service.publish(tenant, agent_id, user)
    assert published["status"] == "published"
    assert service.list_versions(tenant, agent_id)
    assert service.get_agent(tenant, agent_id)["slug"] == "desk"

    conversation = service.create_conversation(tenant, user, agent_id)
    conversation_id = uuid.UUID(str(conversation["id"]))
    uploaded = service.upload(tenant, user, "notes.pdf", "application/pdf", b"%PDF-1.4 hi")
    file_id = uuid.UUID(str(uploaded["id"]))
    assert service.get_file(tenant, user, file_id)["status"] == "ready"
    assert service.file_bytes(tenant, user, file_id)[0].startswith(b"%PDF")
    infected = service.upload(tenant, user, "eicar.txt", "text/plain", EICAR)
    with pytest.raises(ArError):
        service.post_message(
            tenant,
            user,
            conversation_id,
            "see file",
            attachment_ids=[uuid.UUID(str(infected["id"]))],
            schedule=False,
        )
    with pytest.raises(ArError):
        service.upload(tenant, user, "big.pdf", "application/pdf", b"x" * (MAX_UPLOAD_BYTES + 1))
    posted = service.post_message(
        tenant,
        user,
        conversation_id,
        "Hello with a file",
        attachment_ids=[file_id],
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await service.generate(run_id, "Hello with a file", ["notes.pdf"])
    assert service.runs[run_id]["status"] == "completed"
    assert "notes.pdf" in str(service.runs[run_id]["result_summary"])

    slow = service.post_message(
        tenant, user, conversation_id, "Please answer slowly", schedule=False
    )
    slow_id = uuid.UUID(str(slow["run"]["id"]))
    service.cancel_flags.add(slow_id)
    await service.generate(slow_id, "Please answer slowly", [])
    assert service.runs[slow_id]["status"] == "cancelled"

    scheduled = service.post_message(tenant, user, conversation_id, "queued", schedule=True)
    await asyncio.gather(*service.tasks)
    scheduled_id = uuid.UUID(str(scheduled["run"]["id"]))
    assert service.runs[scheduled_id]["status"] == "completed"
    service._schedule = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

    message_id = uuid.UUID(str(posted["message"]["id"]))
    edited = service.edit_message(tenant, user, conversation_id, message_id, "edited text")
    edited_id = uuid.UUID(str(edited["message"]["id"]))
    edited_run = uuid.UUID(str(edited["run"]["id"]))
    service.runs[edited_run]["status"] = "completed"
    service.conversations[conversation_id]["active_run_id"] = None
    activated = service.activate_message(tenant, conversation_id, message_id)
    assert activated["id"] == str(message_id)
    regenerated = service.regenerate(tenant, user, conversation_id, edited_id)
    assert regenerated["run"]["status"] == "queued"
    regen_run = uuid.UUID(str(regenerated["run"]["id"]))
    service.runs[regen_run]["status"] = "completed"
    service.conversations[conversation_id]["active_run_id"] = None

    feedback = service.set_feedback(tenant, user, message_id, "up", "useful")
    assert feedback["rating"] == "up"
    with pytest.raises(ArError):
        service.set_feedback(tenant, user, message_id, "sideways", "")
    service.delete_feedback(tenant, user, message_id)
    with pytest.raises(NotFoundError):
        service.delete_feedback(tenant, user, message_id)

    other = uuid.uuid4()
    share = service.add_share(tenant, user, conversation_id, "user", other)
    assert share["permission"] == "view"
    assert service.list_shares(tenant, user, conversation_id)
    service.delete_share(tenant, user, conversation_id, "user", other)
    exported = service.export_conversation(tenant, user, conversation_id, "json")
    assert exported["format"] == "json"
    markdown = service.export_conversation(tenant, user, conversation_id, "markdown")
    assert "edited text" in str(markdown["body"]) or "Hello" in str(markdown["body"])

    patched = service.patch_conversation(tenant, user, conversation_id, title="Pinned", pinned=True)
    assert patched["title"] == "Pinned"
    assert service.list_conversations(tenant, user)
    assert service.list_runs(tenant, user)
    assert service.get_run(tenant, run_id)["status"] == "completed"
    assert service.list_steps(tenant, run_id) == []
    with pytest.raises(ArError):
        service.cancel_run(tenant, user, run_id)

    api_agent = uuid.UUID(str(service.list_agents(tenant, user)[0]["id"]))
    api_run = service.create_api_run(
        tenant,
        user,
        api_agent,
        "from api",
        callback_url="https://example.test/hook",
        on_behalf_of=None,
        allow_on_behalf=False,
    )
    api_id = uuid.UUID(str(api_run["run"]["id"]))
    await service.generate(api_id, "from api", [])
    assert service.runs[api_id]["status"] == "completed"
    assert service.callbacks

    seen = [str(event["type"]) async for event in service.iter_events(tenant, run_id, 999)]
    assert seen == []

    active = service.post_message(tenant, user, conversation_id, "live", schedule=False)
    active_id = uuid.UUID(str(active["run"]["id"]))

    async def _live() -> list[str]:
        kinds: list[str] = []
        async for event in service.iter_events(tenant, active_id, 0):
            kinds.append(str(event["type"]))
            if event["type"] == "run.completed":
                break
        return kinds

    watcher = asyncio.create_task(_live())
    for _ in range(20):
        if service.subscribers.get(active_id):
            break
        await asyncio.sleep(0.01)
    service.subscribers[active_id][0].put_nowait(
        {
            "id": f"{active_id}:99",
            "seq": 99,
            "type": "run.completed",
            "run_id": str(active_id),
            "conversation_id": str(conversation_id),
            "data": {},
            "ts": "2026-10-20T00:00:00Z",
        }
    )
    assert "run.completed" in await watcher
    assert service.acquire_sse(str(user), 1) is True
    assert service.acquire_sse(str(user), 1) is False
    service.release_sse(str(user))
    service.delete_file(tenant, user, file_id)
    assert service.files[file_id]["status"] == "deleted"
    service.delete_model(tenant, model_id, platform=False)
    service.delete_provider(tenant, provider_id, platform=False)
    service.delete_conversation(tenant, user, conversation_id)
    assert service.conversations[conversation_id]["deleted_at"] is not None
