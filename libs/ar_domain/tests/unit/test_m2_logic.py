"""Pure M2 behaviour: aliases, usage, files, branches, budgets."""

from datetime import UTC, datetime

from ar_domain.agents.logic import AgentView, assistant_definition, can_see_agent, can_start_run
from ar_domain.conversations.logic import MessageNode, activate_branch
from ar_domain.files.logic import EICAR, FileView, can_read_file, mime_allowed, scan_bytes
from ar_domain.models.logic import AliasRef, provider_url_denied, resolve_alias
from ar_domain.runs.logic import (
    assemble_context,
    budget_exceeded,
    sign_run_callback,
    tools_not_supported,
)
from ar_domain.usage.logic import UsageRecord, record_usage, rollup_daily
from ar_ingest.workflows.file_process import process_upload
from ar_model_gateway.breaker import Breaker
from ar_runtime.workflows.agent_run import RunRequest, advance, workflow_id
from ar_system.workflows.usage_rollup import rollup
from ar_testing.factories.chat import agent_factory, provider_factory


def test_factories_and_resolution_order() -> None:
    provider = provider_factory()
    agent = agent_factory(visibility="private", owner_user_id="user-1")
    assert provider["kind"] == "fake"
    assert agent["slug"] == "assistant"
    rows = [
        AliasRef(None, "reasoning", "chat", "platform", (), "active", {}),
        AliasRef("tenant", "reasoning", "chat", "tenant-model", (), "active", {}),
    ]
    found = resolve_alias(rows, "tenant", "reasoning")
    assert found is not None and found.primary_model_id == "tenant-model"
    assert resolve_alias(rows, "other", "reasoning") is not None
    assert resolve_alias(rows, "other", "reasoning").primary_model_id == "platform"  # type: ignore[union-attr]


def test_ssrf_allows_loopback_only_in_dev() -> None:
    deny = ("10.0.0.0/8", "127.0.0.0/8", "192.168.0.0/16")
    assert provider_url_denied("http://10.1.1.1/v1", deny, allow_loopback=True)
    assert not provider_url_denied("http://127.0.0.1:8099/v1", deny, allow_loopback=True)
    assert provider_url_denied("http://127.0.0.1:8099/v1", deny, allow_loopback=False)
    assert not provider_url_denied("http://fake-llm:8099/v1", deny, allow_loopback=True)
    assert provider_url_denied("not a url", deny, allow_loopback=True)


def test_usage_dedupe_and_kolkata_midnight() -> None:
    store: dict[tuple[str, str], UsageRecord] = {}
    before = UsageRecord(
        "t",
        datetime(2026, 10, 20, 18, 29, tzinfo=UTC),
        "runs",
        1,
        0,
        "k1",
    )
    after = UsageRecord(
        "t",
        datetime(2026, 10, 20, 18, 31, tzinfo=UTC),
        "runs",
        2,
        0,
        "k2",
    )
    assert record_usage(store, before)
    assert not record_usage(store, before)
    assert record_usage(store, after)
    days = rollup_daily([before, after], "Asia/Kolkata")
    assert [row.day for row in days] == ["2026-10-20", "2026-10-21"]
    assert rollup([before, after], "Asia/Kolkata") == days


def test_visibility_files_and_branches() -> None:
    view = AgentView("t", "user", None, "private", "published", False)
    assert can_see_agent(view, tenant_id="t", user_id="user", team_ids=set(), manage_all=False)
    assert not can_see_agent(view, tenant_id="t", user_id="other", team_ids=set(), manage_all=False)
    assert can_start_run(view, can_see=True)
    assert not mime_allowed("application/x-msdownload")
    assert scan_bytes(EICAR, scanner="clamav") == "infected"
    assert process_upload(b"hello", scanner="none")["scan_status"] == "skipped"
    file = FileView("t", "user", None, "ready")
    assert can_read_file(
        file, tenant_id="t", user_id="user", conversation_owner=False, read_all=False
    )
    flags = activate_branch(
        [
            MessageNode("a", None, True),
            MessageNode("b", "a", False),
            MessageNode("c", "a", True),
        ],
        "b",
    )
    assert flags["b"] is True
    assert flags["c"] is False


def test_runtime_loop_and_callback() -> None:
    definition = assistant_definition()
    assert not tools_not_supported(definition)
    request = RunRequest("1", definition, "hello")
    assert advance(request, definition["budget"]) == "completed"  # type: ignore[arg-type]
    request.cancelled = True
    assert advance(request, definition["budget"]) == "cancelled"  # type: ignore[arg-type]
    tooled = advance(
        RunRequest("2", {"tools": [{"server": "control"}]}, "hi"),
        {
            "max_steps": 8,
            "max_tokens": 10,
            "max_cost_micros": 1,
            "max_wall_clock_s": 10,
            "max_tool_calls": 8,
        },
    )
    assert tooled == "completed"
    assert workflow_id("abc") == "run-abc"
    assert (
        budget_exceeded(
            steps=9,
            tokens=1,
            cost_micros=0,
            elapsed_s=0,
            tool_calls=0,
            budget={
                "max_steps": 8,
                "max_tokens": 10,
                "max_cost_micros": 1,
                "max_wall_clock_s": 10,
                "max_tool_calls": 0,
            },
        )
        == "max_steps"
    )
    context = assemble_context(instructions="Be brief.", history=[], attachment_names=["notes.pdf"])
    assert "notes.pdf" in context[0]["content"]
    signature = sign_run_callback("secret", b"{}", 10)
    assert signature.startswith("t=10,v1=")
    breaker = Breaker(threshold=2, reset_s=10)
    assert breaker.allow(0)
    breaker.failure(0)
    breaker.failure(1)
    assert breaker.state == "open"
    assert not breaker.allow(5)
    assert breaker.allow(20)
    breaker.success()
    assert breaker.state == "closed"
