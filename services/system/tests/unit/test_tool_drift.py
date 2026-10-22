"""Drift check marks a changed manifest and does not adopt it."""

from ar_domain.chat.service import ChatService
from ar_system.workflows.tool_drift_check import run_drift_check


def test_drift_workflow_requests_review() -> None:
    store = ChatService()
    server = next(row for row in store.tool_servers.values() if row.get("slug") == "tickets")
    version = store.tool_server_versions[server["current_version_id"]]
    original = version["manifest_hash"]
    version["upstream_manifest"] = {"tools": ["create_ticket", "surprise"]}
    changed = run_drift_check(store)
    assert changed
    assert server["status"] == "pending_review"
    assert version["manifest_hash"] == original
    assert any(event["topic"] == "tool_server.review_requested" for event in store.domain_events)
