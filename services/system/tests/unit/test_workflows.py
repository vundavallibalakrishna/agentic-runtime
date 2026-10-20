"""System workflow decisions do not need Temporal to be covered."""

import asyncio

from ar_common.errors import ForbiddenError
from ar_system.subscribers import build_registry
from ar_system.subscribers.cache_invalidation import invalidate
from ar_system.subscribers.notifications import handle as note_handle
from ar_system.subscribers.webhooks import handle as hook_handle
from ar_system.workflows.notification_fanout import notices_for
from ar_system.workflows.outbox_relay import RelayEvent, relay_once, should_continue_as_new
from ar_system.workflows.tenant_deletion import deletion_plan
from ar_system.workflows.tenant_provisioning import ProvisionRequest, provision_plan
from ar_system.workflows.webhook_delivery import delivery_outcome, event_body, prepare_delivery


def test_provision_deletion_and_notices() -> None:
    created = provision_plan(
        None,
        ProvisionRequest("acme", "Acme", "enterprise", "a@b.c", tenant_id="t1"),
        ["seed"],
    )
    assert created.created and created.invited and created.hooks == ["seed"]
    again = provision_plan("t1", ProvisionRequest("acme", "Acme", "enterprise", "a@b.c"), [])
    assert not again.created
    assert deletion_plan(grace_elapsed=False, resumed=False).status == "deleting"
    assert deletion_plan(grace_elapsed=True, resumed=False).status == "deleted"
    assert deletion_plan(grace_elapsed=True, resumed=True).resume
    notices = notices_for("invitation.created", {"email": "a@b.c"})
    assert notices[0].email == "a@b.c"
    assert notices_for("approval.requested", {})[0].kind == "approval_requested"
    assert notices_for("other", {}) == []


def test_relay_webhook_and_subscribers() -> None:
    body = event_body({"display_name": "Ava", "nested": {"max_steps": 1}})
    assert b"displayName" in body
    assert b"maxSteps" in body
    url, signature = prepare_delivery(
        secret="signing-secret",  # noqa: S106
        body=body,
        timestamp=1,
        url="https://example.com/hook",
        allow_private=True,
    )
    assert url.startswith("https://") and signature.startswith("t=")
    try:
        prepare_delivery(
            secret="signing-secret",  # noqa: S106
            body=body,
            timestamp=1,
            url="http://127.0.0.1/hook",
            allow_private=False,
        )
    except ForbiddenError:
        pass
    else:
        raise AssertionError("private webhook targets are rejected")
    assert delivery_outcome(204, 1) == ("succeeded", None)
    assert delivery_outcome(410, 1)[0] == "dead"
    pending, delay = delivery_outcome(500, 1)
    assert pending == "pending" and delay is not None

    async def boom(event: RelayEvent) -> None:
        del event
        raise RuntimeError("nope")

    async def ok(event: RelayEvent) -> None:
        del event

    published, failed = asyncio.run(
        relay_once(
            [RelayEvent("1", "invitation.created", {}), RelayEvent("2", "other", {})],
            {"invitation.created": [ok], "*": [boom]},
        )
    )
    assert published == [] and len(failed) == 2
    assert should_continue_as_new(1000)
    assert not should_continue_as_new(10)
    event = RelayEvent("1", "invitation.created", {"email": "a@b.c", "principal_id": "u"})
    titles = asyncio.run(note_handle(event))
    assert titles == ["You are invited"]
    assert asyncio.run(hook_handle(event, status_code=500, attempts=2)) == "pending"
    asyncio.run(invalidate(event))
    asyncio.run(invalidate(RelayEvent("2", "role.changed", {})))
    registry = build_registry({"custom": [ok]})
    assert "invitation.created" in registry and "custom" in registry
