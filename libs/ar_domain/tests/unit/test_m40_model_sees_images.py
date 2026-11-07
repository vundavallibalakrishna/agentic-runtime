"""The model sees the images a tool produced. Task: M40-T06.

A tool result can carry a screenshot, a rendered page or a chart. The loop collects
those images and, when a vision-capable model is connected, shows them to the model:
the reasoning model directly when it can read images, otherwise the vision alias,
which describes them. With no vision model the turn is unchanged.
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from typing import TYPE_CHECKING

from ar_domain.demo_ids import demo_id
from ar_domain.tools import agent_loop
from ar_domain.tools.images import build_image_message, collect_images
from ar_testing.demo import demo_store
from ar_testing.stand_in import shared

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

# A real 1x1 PNG. media_type_for reads its \x89PNG signature as image/png.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
NOT_AN_IMAGE = b"plain text, not an image"


def _store_file(store: ChatService, tenant: uuid.UUID, *, name: str, mime: str, data: bytes) -> str:
    """Put a file on the store the way a tool's artifact export does, and return its id."""
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "name": name,
        "mime_type": mime,
        "size_bytes": len(data),
        "status": "ready",
    }
    store.blobs[file_id] = data
    return str(file_id)


def test_collect_images_reads_artifacts_and_presentation() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    chart = _store_file(store, tenant, name="revenue.png", mime="image/png", data=PNG)
    shot = _store_file(store, tenant, name="page.png", mime="image/png", data=PNG)
    structured = {
        "presentation": {"kind": "chart", "files": [{"file_id": chart, "name": "revenue.png"}]},
        "artifacts": [chart, shot],  # chart repeats; it must not be collected twice
    }
    images = collect_images(store, structured, tenant)
    assert [item["file_id"] for item in images] == [chart, shot]
    assert all(item["media_type"] == "image/png" for item in images)
    assert images[0]["data"] == PNG


def test_collect_images_skips_non_images_and_other_tenants() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    other = uuid.uuid4()
    doc = _store_file(store, tenant, name="notes.txt", mime="text/plain", data=NOT_AN_IMAGE)
    foreign = _store_file(store, other, name="secret.png", mime="image/png", data=PNG)
    mine = _store_file(store, tenant, name="mine.png", mime="image/png", data=PNG)
    structured = {"artifacts": [doc, foreign, mine]}
    images = collect_images(store, structured, tenant)
    assert [item["file_id"] for item in images] == [mine]


def test_collect_images_caps_the_number() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    ids = [
        _store_file(store, tenant, name=f"p{index}.png", mime="image/png", data=PNG)
        for index in range(6)
    ]
    images = collect_images(store, {"artifacts": ids}, tenant, max_images=4)
    assert len(images) == 4
    assert [item["file_id"] for item in images] == ids[:4]


def _image(name: str = "revenue.png") -> dict[str, object]:
    return {"file_id": str(uuid.uuid4()), "name": name, "media_type": "image/png", "data": PNG}


def test_a_vision_model_is_shown_the_picture() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    store.allow_loopback = True
    shared().connect(store, tenant, aliases=("reasoning",), capabilities=["vision", "tools"])
    run = {"tenant_id": tenant, "agent_version_id": None}
    message = build_image_message(store, run, [_image()], alias="reasoning")
    assert message is not None and message["role"] == "user"
    parts = message["content"]
    assert isinstance(parts, list)
    assert parts[0]["type"] == "text" and "untrusted" in parts[0]["text"].lower()
    image_part = parts[1]
    assert image_part["type"] == "image_url"
    encoded = base64.standard_b64encode(PNG).decode("ascii")
    assert image_part["image_url"]["url"] == f"data:image/png;base64,{encoded}"


def test_a_text_only_model_gets_a_description_from_the_vision_alias() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    store.allow_loopback = True
    # The reasoning model cannot read images; a separate vision-capable model can.
    shared().connect(store, tenant, script_set="reasoning-text", aliases=("reasoning",))
    shared().connect(
        store,
        tenant,
        script_set="vision-describe",
        aliases=("vision",),
        capabilities=["vision"],
    )
    shared().script(
        "vision-describe",
        [
            {
                "match": {"contains": "Describe this image"},
                "respond": {"text": "A quarterly revenue bar chart."},
            }
        ],
    )
    run = {"tenant_id": tenant, "agent_version_id": None}
    message = build_image_message(store, run, [_image()], alias="reasoning")
    assert message is not None and message["role"] == "user"
    body = message["content"]
    assert isinstance(body, str)
    assert "A quarterly revenue bar chart." in body
    assert "untrusted" in body.lower()


def test_no_vision_model_leaves_the_turn_unchanged() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    store.allow_loopback = True
    shared().connect(store, tenant, aliases=("reasoning",))  # no vision capability anywhere
    run = {"tenant_id": tenant, "agent_version_id": None}
    assert build_image_message(store, run, [_image()], alias="reasoning") is None
    assert build_image_message(store, run, [], alias="reasoning") is None


def _real_store() -> ChatService:
    store = demo_store()
    store.allow_loopback = True
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "stand-in-chat",
        {},
        5.0,
        True,
    )
    return store


def test_the_loop_shows_a_tool_image_to_a_vision_model() -> None:
    store = _real_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    shared().connect(store, tenant, aliases=("reasoning",), capabilities=["vision", "tools"])

    seen_image = {"value": False}
    turns = [
        {
            "text": "",
            "tool_calls": [{"id": "c1", "name": "control__checkpoint", "arguments": {"note": "x"}}],
            "usage": {"tokens_in": 2, "tokens_out": 2},
            "real": True,
        },
        {
            "text": "I can see the chart: revenue rose each quarter.",
            "tool_calls": [],
            "usage": {"tokens_in": 2, "tokens_out": 4},
            "real": True,
        },
    ]
    pending = list(turns)

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del tools, tenant_id, model_alias
        for message in messages:
            content = message.get("content")
            if isinstance(content, list) and any(
                isinstance(part, dict) and part.get("type") == "image_url" for part in content
            ):
                seen_image["value"] = True
        return pending.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]

    def fake_act(
        _store: object,
        _run: object,
        _assistant: object,
        call: dict[str, object],
        _by_name: object,
        _attempt: int,
        *,
        retry: bool,
    ) -> dict[str, object]:
        del retry
        return {
            "failed": False,
            "preview": {"qualified_name": "control.checkpoint", "status": "succeeded"},
            "wrapped": f'<tool_result call="{call.get("id")}">done</tool_result>',
            "images": [{"name": "revenue.png", "media_type": "image/png", "data": PNG}],
        }

    original_act = agent_loop._act
    agent_loop._act = fake_act  # type: ignore[assignment]
    try:
        conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
        posted = store.post_message(
            tenant, user, uuid.UUID(str(conversation["id"])), "Chart the revenue", schedule=False
        )
        run_id = uuid.UUID(str(posted["run"]["id"]))
        asyncio.run(store.generate(run_id, "Chart the revenue", []))
    finally:
        agent_loop._act = original_act  # type: ignore[assignment]

    run = store.runs[run_id]
    assert run["status"] == "completed"
    assert seen_image["value"] is True
    answer = store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"]
    assert "I can see the chart" in str(answer)
