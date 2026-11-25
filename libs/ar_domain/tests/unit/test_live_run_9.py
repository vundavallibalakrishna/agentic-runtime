"""Live rerun: tool deadlines and an interrupted call.

Label: unit
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.settings import get_settings
from ar_domain.tools.gateway_client import _timeout
from ar_domain.tools.pipeline import resolved_timeout_s
from ar_domain.tools.resume import fail_interrupted_tool
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest


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
