"""Live rerun: tool deadlines and an interrupted call.

Label: unit
"""

from __future__ import annotations

import uuid

import pytest

from ar_common.settings import get_settings
from ar_domain.tools.gateway_client import _body, _timeout
from ar_domain.tools.pipeline import ToolPipeline, _call_key, resolved_timeout_s
from ar_domain.tools.resume import fail_interrupted_tool
from ar_testing.demo import demo_store


def test_extract_timeout_follows_the_setting_and_the_client_waits_past_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "document_extract_timeout_s", 480)
    monkeypatch.setattr(settings, "tool_gateway_grace_s", 40)
    version = {"qualified_name": "documents.extract", "timeout_s": 60}
    assert resolved_timeout_s(version) == 480
    assert resolved_timeout_s({"qualified_name": "documents.read", "timeout_s": 60}) == 60
    version_id = uuid.uuid4()
    store = type("Store", (), {"tool_versions": {version_id: version}})()
    assert _timeout(store, {"tool_version_id": version_id}) == 520


def test_an_interrupted_tool_fails_instead_of_staying_on_the_approval_message() -> None:
    store = demo_store()
    run_id = uuid.uuid4()
    message_id = uuid.uuid4()
    call_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "status": "waiting_approval",
        "assistant_message_id": message_id,
        "conversation_id": None,
    }
    store.messages[message_id] = {
        "id": message_id,
        "run_id": run_id,
        "role": "assistant",
        "text": "Waiting for approval before this tool runs.",
        "content": [{"type": "text", "text": "Waiting for approval before this tool runs."}],
        "status": "streaming",
        "tool_calls": [
            {
                "qualified_name": "documents.extract",
                "status": "awaiting_approval",
                "result_preview": "Waiting for approval before this tool runs.",
            }
        ],
    }
    store.tool_calls[call_id] = {
        "id": call_id,
        "run_id": run_id,
        "status": "awaiting_approval",
        "qualified_name": "documents.extract",
    }
    fail_interrupted_tool(store, store.runs[run_id])
    assert store.runs[run_id]["status"] == "failed"
    reply = store.messages[message_id]
    assert reply["status"] == "failed"
    assert "did not finish in time" in str(reply["text"])
    assert "Waiting for approval" not in str(reply["text"])
    assert reply["tool_calls"][0]["status"] == "failed"
    assert store.tool_calls[call_id]["status"] == "failed"


def test_an_approved_call_updates_the_held_row() -> None:
    store = demo_store()
    tenant = uuid.uuid4()
    run_id = uuid.uuid4()
    call_id = uuid.uuid4()
    request = {
        "tenant_id": tenant,
        "run_id": run_id,
        "model_call_id": "call-1",
        "approval_id": uuid.uuid4(),
    }
    version = {"qualified_name": "documents.extract", "id": uuid.uuid4(), "tool_id": uuid.uuid4()}
    key = _call_key(request, "documents.extract")
    store.tool_calls[call_id] = {
        "id": call_id,
        "tenant_id": tenant,
        "run_id": run_id,
        "status": "awaiting_approval",
        "result_preview": "Waiting for approval.",
        "idempotency_key": key,
        "qualified_name": "documents.extract",
    }
    replay = ToolPipeline(store)._replay(dict(request), version)
    assert replay is None
    followed = dict(request)
    ToolPipeline(store)._replay(followed, version)
    assert followed["tool_call_id"] == call_id
    sent = _body({**followed, "tool_call_id": call_id, "arguments": {}})
    assert sent["tool_call_id"] == str(call_id)
    ToolPipeline(store)._stored(
        followed,
        version,
        {"id": version["tool_id"]},
        "succeeded",
        "allow",
        "extracted",
        False,
        0.0,
        None,
    )
    assert list(store.tool_calls) == [call_id]
    assert store.tool_calls[call_id]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_extraction_status_is_written() -> None:
    from ar_domain.durable.extractions_save import save_extractions

    seen: dict[str, object] = {}

    class _Session:
        async def execute(self, _statement: object, params: dict[str, object]) -> None:
            seen.update(params)

    extraction_id = uuid.uuid4()
    await save_extractions(
        _Session(),  # type: ignore[arg-type]
        [
            {
                "id": extraction_id,
                "tenant_id": uuid.uuid4(),
                "document_id": uuid.uuid4(),
                "status": "awaiting_approval",
            }
        ],
    )
    assert seen["status"] == "awaiting_approval"
    assert seen["id"] == extraction_id
