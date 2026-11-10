"""Stage 3 resumable /v1 streams. Proof label: unit.

No network and no model. The run-event stand-in is an in-process Valkey stream.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from ar_domain.db.context import Principal
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.runs.event_bus import ValkeyRunBus, last_event_seq
from ar_testing.demo import demo_application, demo_store
from ar_testing.demo_people import DEV_TENANT_ID


class _Stream:
    def __init__(self) -> None:
        self.rows: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._n = 0

    async def xadd(
        self,
        key: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        del maxlen, approximate
        self._n += 1
        message_id = f"{self._n}-0"
        self.rows.setdefault(key, []).append((message_id, fields))
        return message_id

    async def xrange(
        self,
        key: str,
        min: str = "-",  # noqa: A002
        max: str = "+",  # noqa: A002
    ) -> list[tuple[str, dict[str, str]]]:
        del min, max
        return list(self.rows.get(key, []))


@pytest.mark.asyncio
async def test_last_event_id_replays_the_shared_stream() -> None:
    """Proof label: unit."""
    assert last_event_seq("4") == 4
    assert last_event_seq("run:9") == 9
    store = demo_store()
    bus = ValkeyRunBus("redis://unused", client=_Stream())
    store.event_bus = bus
    tenant = DEV_TENANT_ID
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hello", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    store._emit(store.runs[run_id], "message.completed", {"text": "done"})
    store.runs[run_id]["status"] = "completed"
    if bus._pending:
        await __import__("asyncio").gather(*list(bus._pending))
    store.events[run_id] = []
    seen = [
        int(event["seq"]) async for event in store.iter_events(tenant, run_id, 1, idle_s=0.01)
    ]
    assert seen
    assert 1 not in seen
    assert max(seen) > 1


def test_public_v1_stream_resumes_and_names_its_version() -> None:
    """Proof label: unit."""
    holder: dict[str, Principal | None] = {
        "principal": Principal(
            kind="user",
            id=str(demo_id("admin")),
            tenant_id=demo_id("tenant"),
            permissions=PERMISSION_KEYS,
            team_permissions=frozenset(),
            auth_method="bearer",
            email="admin@dev.local",
            display_name="Admin",
            roles=frozenset({"tenant_admin"}),
        )
    }
    app = demo_application()

    async def resolve(scope: object) -> Principal | None:
        del scope
        return holder["principal"]

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        run = app.state.chat.runs[run_id]
        run["status"] = "completed"
        assistant = app.state.chat.messages[run["assistant_message_id"]]
        assistant["text"] = "4"
        assistant["status"] = "completed"

    app.state.resolve_principal = resolve
    app.state.chat.generate = generate  # type: ignore[method-assign]
    client = TestClient(app)
    version = client.get("/v1")
    assert version.json()["version"] == "1"
    assert version.headers["api-version"] == "1"
    rows = client.get("/api/v1/agents").json()
    data = rows["data"] if "data" in rows else rows["items"]
    agent_id = next(row["id"] for row in data if row["slug"] == "assistant")
    created = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "Stream", "rateLimitRpm": 20, "monthlyQuota": 20},
    )
    headers = {"Authorization": f"Bearer {created.json()['key']}"}
    conversation = client.post("/v1/agents/assistant/conversations", headers=headers)
    sent = client.post(
        f"/v1/agents/assistant/conversations/{conversation.json()['id']}/messages",
        headers={**headers, "Idempotency-Key": "stage3-stream"},
        json={"text": "What is 2 + 2?", "stream": True},
    )
    assert sent.status_code == 200
    assert "text/event-stream" in sent.headers["content-type"]
    assert "4" in sent.text
    assert "id:" in sent.text
    plain = client.post(
        f"/v1/agents/assistant/conversations/{conversation.json()['id']}/messages",
        headers=headers,
        json={"text": "plain"},
    )
    run = plain.json()["id"]
    page = client.get(
        f"/v1/agents/assistant/runs/{run}/events",
        headers={**headers, "Accept": "application/json"},
    )
    assert page.status_code == 200
    assert isinstance(page.json()["items"], list)
    resumed = client.get(
        f"/v1/agents/assistant/runs/{run}/events",
        headers={**headers, "Last-Event-ID": "999"},
    )
    assert resumed.status_code == 200
    assert "text/event-stream" in resumed.headers["content-type"]
    assert "event: run.queued" not in resumed.text
    once = client.post(
        "/v1/agents/assistant:run",
        headers={**headers, "Idempotency-Key": "stage3-once"},
        json={"text": "once", "stream": True},
    )
    assert once.status_code == 200
    assert "4" in once.text
