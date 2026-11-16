"""A scoped API key does not grow into the owner's role after a reload."""

from __future__ import annotations

import uuid

from ar_domain.approvals.pending import hold
from ar_domain.chat.service import demo_id
from ar_domain.runs.request import asked, permissions_of
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.resume import _resume
from ar_testing.demo import demo_store


def test_create_approval_resume_and_reload_keep_the_scope(monkeypatch) -> None:
    store = demo_store()
    admin = demo_id("admin")
    store.user_roles[admin] = {"tenant_admin"}
    agent = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    posted = store.create_api_run(
        demo_id("tenant"),
        admin,
        uuid.UUID(str(agent["id"])),
        "look this up",
        callback_url=None,
        on_behalf_of=None,
        allow_on_behalf=False,
        permissions=["chat:use"],
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]  # type: ignore[index]
    assert run["permissions"] == ["chat:use"]
    assert asked(run, "permissions") == ["chat:use"]
    request = {"user_id": admin, "tenant_id": run["tenant_id"], "run_id": run["id"]}
    assert ToolPipeline(store)._caller_permissions(request) == ["chat:use"]

    seen: dict[str, object] = {}

    def execute(_store: object, body: dict[str, object]) -> dict[str, object]:
        seen.update(body)
        return {"status": "succeeded", "result_preview": "done"}

    monkeypatch.setattr("ar_domain.tools.gateway_client.execute_tool", execute)
    approval_id = uuid.uuid4()
    run["status"] = "waiting_approval"
    hold(
        run,
        {
            "approval_id": approval_id,
            "tool_version_id": uuid.uuid4(),
            "arguments": {},
            "args_hash": "abc",
            "model_call_id": "call-1",
        },
    )
    _resume(store, run, {"id": approval_id, "status": "approved", "tool_call_id": uuid.uuid4()})
    assert seen["permissions"] == ["chat:use"]

    # Another process loads the run columns. The loose field is not one of them.
    del run["permissions"]
    assert permissions_of(run) == ["chat:use"]
    assert ToolPipeline(store)._caller_permissions(request) == ["chat:use"]


def test_an_explicit_scope_does_not_gain_pack_permissions() -> None:
    from ar_domain.records.memory import bucket
    from ar_testing.demo import demo_store as fresh

    store = fresh()
    admin = demo_id("admin")
    tenant = demo_id("tenant")
    store.user_roles[admin] = {"tenant_admin"}
    bucket(store, "pack_permissions")["grc"] = {"keys": ["grc.catalogues:manage"]}
    bucket(store, "pack_flags")[uuid.uuid4()] = {
        "tenant_id": tenant,
        "pack_id": "grc",
        "enabled": True,
    }
    scoped = ToolPipeline(store)._caller_permissions(
        {"user_id": admin, "tenant_id": tenant, "permissions": ["chat:use"]}
    )
    assert scoped == ["chat:use"]
    kept = ToolPipeline(store)._caller_permissions(
        {
            "user_id": admin,
            "tenant_id": tenant,
            "permissions": ["chat:use", "grc.catalogues:manage"],
        }
    )
    assert kept == ["chat:use", "grc.catalogues:manage"]
    opened = ToolPipeline(store)._caller_permissions({"user_id": admin, "tenant_id": tenant})
    assert "grc.catalogues:manage" in opened
