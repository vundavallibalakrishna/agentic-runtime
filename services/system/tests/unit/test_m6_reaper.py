"""The reaper activity is safe to repeat."""

from datetime import timedelta

from temporalio.worker import Worker

from ar_common.time import utcnow
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.sandboxes.runtime import ensure_scope
from ar_system.workflows.sandbox_reaper import SandboxReaperWorkflow, bind_store, reap_sandboxes


async def test_reaper_suspends_once(temporal_env: object) -> None:
    store = ChatService()
    row = ensure_scope(
        store,
        tenant_id=demo_id("tenant"),
        template_slug="python-data",
        scope="conversation",
        scope_key="conv:reaper",
        conversation_id=None,
        agent_id=None,
        user_id=demo_id("admin"),
    )
    store.sandbox_templates[row["template_id"]]["idle_suspend_s"] = 1
    store.sandbox_templates[row["template_id"]]["max_lifetime_s"] = 10**9
    row["last_active_at"] = utcnow() - timedelta(seconds=30)
    bind_store(store)
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="m6-reaper",
        workflows=[SandboxReaperWorkflow],
        activities=[reap_sandboxes],
    ):
        first = await client.execute_workflow(
            SandboxReaperWorkflow.run,
            id="m6-reaper",
            task_queue="m6-reaper",
        )
    assert first["suspended"] == 1
    second = await reap_sandboxes()
    assert second["suspended"] == 0
    assert row["status"] == "suspended"


async def test_reaper_without_a_store() -> None:
    from ar_system.workflows import sandbox_reaper

    previous = sandbox_reaper._STORE
    sandbox_reaper._STORE = None
    try:
        assert await reap_sandboxes() == {"suspended": 0, "terminated": 0}
    finally:
        sandbox_reaper._STORE = previous
