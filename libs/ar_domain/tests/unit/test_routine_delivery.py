"""A routine's result leaves the product: by email and by signed webhook.

The mail server and the receiving address are real sockets on this machine, so a
delivery counted as sent is one that arrived.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import StreamRequestHandler, ThreadingTCPServer
from typing import TYPE_CHECKING

import orjson
import pytest

from ar_common.errors import UnavailableError, ValidationFailedError
from ar_common.settings import get_settings, set_settings
from ar_domain.agents.access import Actor
from ar_domain.approvals.service import ApprovalBook
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.engine import (
    accept_routine_event,
    complete_routine_event,
    prepare_routine_run,
    release_delivery,
)
from ar_domain.tools.handlers import dispatch
from ar_domain.tools.named_secrets import read_named_secret
from ar_domain.tools.seed_tools import shipped_tools
from ar_testing.demo import demo_store
from ar_testing.demo_tenant import seed_demo

if TYPE_CHECKING:
    from collections.abc import Iterator

_TEXT = "The week in brief."


class _Mail(StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"220 ready\r\n")
        lines: list[str] | None = None
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").rstrip("\r\n")
            if lines is not None:
                if line == ".":
                    self.server.messages.append("\n".join(lines))  # type: ignore[attr-defined]
                    lines = None
                    self.wfile.write(b"250 ok\r\n")
                else:
                    lines.append(line)
            elif line.upper().startswith("DATA"):
                lines = []
                self.wfile.write(b"354 go\r\n")
            elif line.upper().startswith("QUIT"):
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


class _Hook(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.calls.append((dict(self.headers.items()), body))  # type: ignore[attr-defined]
        self.send_response(self.server.answer)  # type: ignore[attr-defined]
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


class _Engine:
    """Stands where the workflow engine's client is: it keeps what it was asked to start."""

    def __init__(self) -> None:
        self.started: list[tuple[str, dict[str, object]]] = []

    async def start_workflow(self, name: str, payload: dict[str, object], **_kw: object) -> None:
        self.started.append((name, payload))


@pytest.fixture
def mail() -> Iterator[ThreadingTCPServer]:
    server = ThreadingTCPServer(("127.0.0.1", 0), _Mail)
    server.messages = []  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = get_settings()
    set_settings(
        before.model_copy(
            update={
                "smtp_host": "127.0.0.1",
                "smtp_port": server.server_address[1],
                "smtp_from": "routines@install.test",
                "egress_allow_loopback": True,
            }
        )
    )
    yield server
    set_settings(before)
    server.shutdown()
    server.server_close()


@pytest.fixture
def hook() -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Hook)
    server.calls = []  # type: ignore[attr-defined]
    server.answer = 204  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = get_settings()
    set_settings(before.model_copy(update={"egress_allow_loopback": True}))
    yield server
    set_settings(before)
    server.shutdown()
    server.server_close()


def _actor() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=frozenset(
            {
                "routines:create",
                "routines:manage_all",
                "approvals:decide",
                "approvals:grant_standing",
                "agents:manage_all",
            }
        ),
        display_name="Admin",
    )


def _store() -> ChatService:
    store = demo_store()
    seed_demo(store)
    return store


def _ran(  # type: ignore[type-arg]
    store: ChatService,
    delivery: list[dict[str, object]],
    *,
    name: str = "Digest",
    quiet: bool = False,
) -> dict:
    """Create a routine, run it once with a finished answer, and complete the event.

    With ``quiet`` the run called ``routines.nothing_to_report`` before it answered.
    """
    agent = store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    created = RoutineBook(store).create(
        _actor(),
        {
            "name": name,
            "instructions": "Write the weekly digest.",
            "agent_id": agent["id"],
            "trigger": {"type": "manual"},
            "delivery": delivery,
        },
    )
    routine_id = uuid.UUID(str(created["id"]))
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="manual",
        idempotency_key=str(uuid.uuid4()),
        envelope={"type": "manual", "data": {}},
    )
    event_id = uuid.UUID(str(accepted["event_id"]))
    prepared = prepare_routine_run(store, routine_id, event_id)
    run = store.runs[uuid.UUID(str(prepared["run_id"]))]
    run["status"] = "completed"
    run["result_summary"] = _TEXT
    if quiet:
        call_id = uuid.uuid4()
        store.tool_calls[call_id] = {
            "id": call_id,
            "tenant_id": run["tenant_id"],
            "run_id": run["id"],
            "qualified_name": "routines.nothing_to_report",
            "status": "succeeded",
        }
    done = complete_routine_event(store, event_id)
    return {"routine_id": routine_id, "event_id": event_id, "run": run, "done": done}


def _posts(store: ChatService) -> list[dict[str, object]]:
    return [row for row in store.channel_posts.values() if row.get("direction") == "outbound"]


def test_an_email_approved_in_advance_arrives(mail: ThreadingTCPServer) -> None:
    store = _store()
    ran = _ran(store, [{"type": "email", "channel": "lead@customer.test", "pre_approved": True}])
    assert ran["done"]["status"] == "completed"
    [message] = mail.messages  # type: ignore[attr-defined]
    assert "To: lead@customer.test" in message
    assert "Subject: Digest" in message
    assert "From: routines@install.test" in message
    assert _TEXT in message
    [post] = _posts(store)
    assert post["status"] == "posted"
    # The id on the record is the one the message carried, not one made up afterwards.
    assert str(post["external_message_id"]) in message


def test_an_email_waits_for_its_owner_and_is_sent_once(mail: ThreadingTCPServer) -> None:
    store = _store()
    store.temporal_client = _Engine()
    ran = _ran(store, [{"type": "email", "channel": "lead@customer.test"}])
    assert ran["done"]["status"] == "waiting"
    assert mail.messages == []  # type: ignore[attr-defined]
    approval_id = uuid.UUID(str(ran["done"]["deliveries"][0]["approval_id"]))
    book = ApprovalBook(store)
    [listed] = book.list_items(
        _actor(), scope="to_decide", status="pending", agent_id=None, risk_class=None
    )
    assert str(listed["id"]) == str(approval_id)
    row = store.approvals[approval_id]
    assert row["qualified_name"] == "delivery.email_send"
    assert row["run_id"] == ran["run"]["id"]
    assert store.tool_calls[row["tool_call_id"]]["status"] == "awaiting_approval"
    # Nothing leaves before the decision, and a release before it sends nothing.
    assert release_delivery(store, approval_id) == {"result": "waiting"}
    book.decide(
        _actor(),
        approval_id,
        {"decision": "approve", "args_hash": row["args_hash"]},
        stepped_up=False,
    )
    assert store.temporal_client.started == [
        ("RoutineDeliveryWorkflow", {"approval_id": str(approval_id)})
    ]
    assert mail.messages == []  # type: ignore[attr-defined]
    first = release_delivery(store, approval_id)
    second = release_delivery(store, approval_id)
    assert first["result"] == "posted"
    assert second == {"result": "posted", "duplicate": True}
    assert len(mail.messages) == 1  # type: ignore[attr-defined]
    assert store.tool_calls[row["tool_call_id"]]["status"] == "succeeded"
    event = store.routine_events[ran["event_id"]]
    assert [item["result"] for item in event["detail"]["deliveries"]] == ["posted"]
    assert store.routines[ran["routine_id"]]["consecutive_failures"] == 0


def test_a_refused_delivery_sends_nothing(mail: ThreadingTCPServer) -> None:
    store = _store()
    ran = _ran(store, [{"type": "email", "channel": "lead@customer.test"}])
    approval_id = uuid.UUID(str(ran["done"]["deliveries"][0]["approval_id"]))
    row = store.approvals[approval_id]
    ApprovalBook(store).decide(
        _actor(),
        approval_id,
        {"decision": "reject", "args_hash": row["args_hash"]},
        stepped_up=False,
    )
    assert release_delivery(store, approval_id) == {"result": "waiting"}
    assert mail.messages == []  # type: ignore[attr-defined]
    event = store.routine_events[ran["event_id"]]
    assert [item["result"] for item in event["detail"]["deliveries"]] == ["rejected"]
    assert store.routines[ran["routine_id"]]["consecutive_failures"] == 0


def test_an_approval_with_no_engine_is_refused_in_words(mail: ThreadingTCPServer) -> None:
    store = _store()
    store.temporal_client = None
    ran = _ran(store, [{"type": "email", "channel": "lead@customer.test"}])
    approval_id = uuid.UUID(str(ran["done"]["deliveries"][0]["approval_id"]))
    row = store.approvals[approval_id]
    with pytest.raises(UnavailableError):
        ApprovalBook(store).decide(
            _actor(),
            approval_id,
            {"decision": "approve", "args_hash": row["args_hash"]},
            stepped_up=False,
        )
    assert mail.messages == []  # type: ignore[attr-defined]


def test_no_mail_server_is_a_failure_that_says_so() -> None:
    before = get_settings()
    set_settings(before.model_copy(update={"smtp_host": ""}))
    try:
        store = _store()
        ran = _ran(
            store, [{"type": "email", "channel": "lead@customer.test", "pre_approved": True}]
        )
    finally:
        set_settings(before)
    assert ran["done"]["status"] == "failed"
    [outcome] = ran["done"]["deliveries"]
    assert outcome["result"] == "failed"
    assert "AR_SMTP_HOST" in outcome["reason"]
    [post] = _posts(store)
    assert post["status"] == "failed"
    assert post["external_message_id"] is None
    assert ran["run"]["error"] == {"code": "delivery_failed"}
    assert store.routines[ran["routine_id"]]["consecutive_failures"] == 1


def test_a_webhook_is_signed_and_its_secret_is_kept_as_a_secret(
    hook: ThreadingHTTPServer,
) -> None:
    store = _store()
    url = f"http://127.0.0.1:{hook.server_address[1]}/in"
    ran = _ran(
        store,
        [
            {
                "type": "webhook",
                "pre_approved": True,
                "config": {"url": url, "secret": "s3cret-value"},
            }
        ],
    )
    assert ran["done"]["status"] == "completed"
    [(headers, body)] = hook.calls  # type: ignore[attr-defined]
    sent = orjson.loads(body)
    assert sent["text"] == _TEXT
    assert sent["routineId"] == str(ran["routine_id"])
    assert sent["runId"] == str(ran["run"]["id"])
    stamp, _, digest = headers["X-Signature"].partition(",v1=")
    expected = hmac.new(b"s3cret-value", stamp[2:].encode() + b"." + body, hashlib.sha256)
    assert digest == expected.hexdigest()
    [post] = _posts(store)
    assert headers["X-Delivery-Id"] == str(post["id"]) == post["external_message_id"]
    [target] = store.routines[ran["routine_id"]]["delivery"]
    assert "secret" not in target["config"]
    assert read_named_secret(store, demo_id("tenant"), target["config"]["secret_name"]) == (
        "s3cret-value"
    )
    assert "s3cret-value" not in json.dumps(
        RoutineBook(store).detail(_actor(), ran["routine_id"]), default=str
    )


def test_a_webhook_the_address_refuses_is_a_failure(hook: ThreadingHTTPServer) -> None:
    hook.answer = 500  # type: ignore[attr-defined]
    store = _store()
    url = f"http://127.0.0.1:{hook.server_address[1]}/in"
    ran = _ran(store, [{"type": "webhook", "pre_approved": True, "config": {"url": url}}])
    assert ran["done"]["status"] == "failed"
    assert ran["done"]["deliveries"][0]["reason"] == "The address answered 500."


def test_a_private_address_is_not_called() -> None:
    store = _store()
    ran = _ran(
        store,
        [{"type": "webhook", "pre_approved": True, "config": {"url": "http://169.254.169.254/x"}}],
    )
    assert ran["done"]["deliveries"][0]["result"] == "failed"
    assert "may not be called" in ran["done"]["deliveries"][0]["reason"]


def test_a_target_with_no_sender_fails_instead_of_being_recorded_as_sent() -> None:
    store = _store()
    ran = _ran(store, [{"type": "slack", "channel": "#general", "pre_approved": True}])
    [outcome] = ran["done"]["deliveries"]
    assert outcome["result"] == "failed"
    assert "slack" in outcome["reason"]
    assert _posts(store)[0]["status"] == "failed"


def test_a_failed_run_delivers_nothing(mail: ThreadingTCPServer) -> None:
    store = _store()
    agent = store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    created = RoutineBook(store).create(
        _actor(),
        {
            "name": "Digest",
            "instructions": "Write the weekly digest.",
            "agent_id": agent["id"],
            "trigger": {"type": "manual"},
            "delivery": [{"type": "email", "channel": "lead@customer.test", "pre_approved": True}],
        },
    )
    routine_id = uuid.UUID(str(created["id"]))
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="manual",
        idempotency_key="failed",
        envelope={"type": "manual"},
    )
    event_id = uuid.UUID(str(accepted["event_id"]))
    prepare_routine_run(store, routine_id, event_id)
    done = complete_routine_event(store, event_id, run_status="failed")
    assert done == {"status": "failed", "event_id": str(event_id), "deliveries": []}
    assert mail.messages == []  # type: ignore[attr-defined]


def _report_only(**more: object) -> dict[str, object]:
    return {
        "type": "email",
        "channel": "lead@customer.test",
        "pre_approved": True,
        "when": "something_to_report",
        **more,
    }


def test_a_report_only_delivery_is_not_sent_when_the_run_had_nothing_to_report(
    mail: ThreadingTCPServer,
) -> None:
    store = _store()
    done = _ran(store, [_report_only(), {"type": "conversation"}], quiet=True)["done"]
    assert done["status"] == "completed"
    assert done["deliveries"][0] == {
        "target": "email",
        "result": "skipped",
        "reason": "The run had nothing to report.",
    }
    assert mail.messages == []  # type: ignore[attr-defined]
    assert _posts(store) == []
    # Nothing was held for anyone to approve, and a quiet run is not a failure.
    assert not [row for row in store.approvals.values() if row.get("status") == "pending"]
    routine = next(row for row in store.routines.values() if row["name"] == "Digest")
    assert routine["consecutive_failures"] == 0


def test_a_report_only_delivery_is_sent_when_the_run_reports(mail: ThreadingTCPServer) -> None:
    store = _store()
    done = _ran(store, [_report_only()])["done"]
    assert done["deliveries"][0]["result"] == "posted"
    assert len(mail.messages) == 1  # type: ignore[attr-defined]


def test_a_delivery_set_to_always_is_sent_on_a_quiet_run_too(mail: ThreadingTCPServer) -> None:
    store = _store()
    always = {"type": "email", "channel": "lead@customer.test", "pre_approved": True}
    done = _ran(store, [always], quiet=True)["done"]
    assert done["deliveries"][0]["result"] == "posted"
    assert len(mail.messages) == 1  # type: ignore[attr-defined]


def test_a_report_only_delivery_that_is_not_approved_in_advance_is_not_held_on_a_quiet_run() -> (
    None
):
    store = _store()
    done = _ran(store, [_report_only(pre_approved=False)], quiet=True)["done"]
    assert done["deliveries"][0]["result"] == "skipped"
    assert not [row for row in store.approvals.values() if row.get("status") == "pending"]


def test_a_delivery_with_an_unknown_when_is_refused() -> None:
    store = _store()
    agent = store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    with pytest.raises(ValidationFailedError):
        RoutineBook(store).create(
            _actor(),
            {
                "name": "Bad when",
                "instructions": "Say hello.",
                "agent_id": agent["id"],
                "trigger": {"type": "manual"},
                "delivery": [{"type": "email", "channel": "a@b.test", "when": "sometimes"}],
            },
        )


def test_the_tool_says_what_it_does_for_a_routine_run_and_for_any_other() -> None:
    store = _store()
    who = {"_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin")}
    conversation = store.create_conversation(demo_id("tenant"), demo_id("admin"), None)
    posted = store.post_message(
        demo_id("tenant"),
        demo_id("admin"),
        uuid.UUID(str(conversation["id"])),
        "Hi",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    plain = dispatch(
        store, "builtin://routines", "nothing_to_report", {**who, "_run_id": run_id}, ""
    )
    assert plain["is_error"] is False
    assert "not started by a routine" in plain["text"]
    store.runs[run_id]["trigger"] = "routine"
    noted = dispatch(
        store, "builtin://routines", "nothing_to_report", {**who, "_run_id": run_id}, ""
    )
    assert "will not be" in noted["text"]
    assert "routines.nothing_to_report" in shipped_tools()
