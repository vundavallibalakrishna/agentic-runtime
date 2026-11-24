"""Approval cards, the review link and signed webhook delivery.

Label: unit
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING

import orjson
import pytest

from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.approvals.announce import approver_emails
from ar_domain.approvals.review_link import (
    decide_review,
    issue_review_token,
    review_url,
    view_approval,
)
from ar_domain.approvals.service import ApprovalBook
from ar_domain.channels.cards import post_cards
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.webhooks.book import WebhookBook
from ar_domain.webhooks.delivery import attempt, dispatch_public_event
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def _actor() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
        display_name="Ada",
    )


def _pending(
    store: ChatService, *, arguments: dict[str, object] | None = None
) -> dict[str, object]:
    actor = _actor()
    run_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "status": "waiting_approval",
        "conversation_id": None,
    }
    store.events[run_id] = []
    return ApprovalBook(store).create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=run_id,
        agent_id=None,
        tool_call_id=uuid.uuid4(),
        qualified_name="pack.example",
        risk_class="W2",
        args_hash="hash-1",
        arguments=arguments or {"name": "Ada", "count": 2},
        requirement={"approvers": {"mode": "requester"}, "ttl_s": 3600},
        reasons=["ask"],
        preview={"title": "Send", "summary": "A request"},
    )


def test_review_link_shows_one_item_and_keeps_an_edit() -> None:
    store = demo_store()
    row = _pending(store)
    approver = demo_id("admin")
    token = issue_review_token(row["id"], row["tenant_id"], approver, utcnow() + timedelta(hours=1))
    viewed = view_approval(store, token)
    assert viewed["qualified_name"] == "pack.example"
    assert viewed["arguments"] == {"name": "Ada", "count": 2}
    assert "name" in viewed["schema"]["properties"]
    assert review_url(token).endswith(f"/review/{token}")
    decided = decide_review(
        store,
        token,
        {
            "decision": "approve",
            "comment": "fixed the name",
            "arguments": {"name": "Grace", "count": 2},
        },
        require_session=False,
        session_user_id=None,
        stepped_up=True,
    )
    assert decided["status"] == "pending"
    assert decided["arguments"]["name"] == "Grace"
    original = store.approvals[row["id"]]
    assert original["status"] == "rejected"
    assert original["arguments"]["name"] == "Ada"


def test_a_bad_review_token_is_not_an_approval() -> None:
    store = demo_store()
    _pending(store)
    with pytest.raises(Exception, match="review link"):
        view_approval(store, "not-a-token")


def test_approval_email_uses_the_approver_not_a_fixed_address() -> None:
    store = demo_store()
    store.user_emails[demo_id("admin")] = "ada@example.com"
    emails = approver_emails(store, [str(demo_id("admin"))])
    assert emails == ["ada@example.com"]
    assert "approvals@dev.local" not in emails


def test_a_channel_binding_records_an_interactive_card() -> None:
    store = demo_store()
    integration_id = uuid.uuid4()
    store.channel_integrations[integration_id] = {
        "id": integration_id,
        "tenant_id": demo_id("tenant"),
        "kind": "slack",
        "name": "work",
        "status": "active",
    }
    row = _pending(store)
    cards = [item for item in store.channel_posts.values() if item.get("kind") == "slack"]
    assert cards
    detail = cards[0]["detail"]
    blocks = detail["card"]["blocks"]
    actions = {block["action_id"] for block in blocks}
    assert {"approve", "reject", "review"} <= actions
    assert str(detail["review_url"]).startswith("http")
    assert str(row["id"]) in blocks[0]["value"]


def test_cards_are_not_posted_without_a_binding() -> None:
    store = demo_store()
    _pending(store)
    assert store.channel_posts == {}


class _Hook(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.calls.append((dict(self.headers), body))  # type: ignore[attr-defined]
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def test_webhook_delivery_is_signed_and_can_be_replayed() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Hook)
    server.calls = []  # type: ignore[attr-defined]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        store = demo_store()
        tenant = demo_id("tenant")
        book = WebhookBook(store)
        created = book.create(
            tenant, demo_id("admin"), "sink", "https://example.com/hook", ["run.completed"]
        )
        assert "secret" in created
        assert "secret" not in book.get(tenant, uuid.UUID(str(created["id"])))
        hook_id = uuid.UUID(str(created["id"]))
        store.outbound_webhooks[hook_id]["url"] = f"http://127.0.0.1:{server.server_address[1]}/in"
        count = dispatch_public_event(
            store, tenant, "run.completed", {"run_id": "r1", "status": "completed"}
        )
        assert count == 1
        assert server.calls  # type: ignore[attr-defined]
        headers, body = server.calls[0]  # type: ignore[attr-defined]
        signature = headers["X-AR-Signature"]
        stamp, _, digest = signature.partition(",v1=")
        expected = hmac.new(
            created["secret"].encode(),
            stamp.removeprefix("t=").encode() + b"." + body,
            hashlib.sha256,
        )
        assert digest == expected.hexdigest()
        sent = orjson.loads(body)
        assert sent["topic"] == "run.completed"
        assert sent["payload"]["runId"] == "r1"
        delivery_id = next(iter(store.webhook_deliveries))
        store.webhook_deliveries[delivery_id]["status"] = "failed"
        server.calls.clear()  # type: ignore[attr-defined]
        again = attempt(store, delivery_id)
        assert again["status"] == "succeeded"
        assert len(server.calls) == 1  # type: ignore[attr-defined]
    finally:
        server.shutdown()


def test_post_cards_helper_is_a_no_op_without_bindings() -> None:
    store = demo_store()
    assert post_cards(store, {"id": uuid.uuid4(), "tenant_id": demo_id("tenant")}, [], {}) == []
