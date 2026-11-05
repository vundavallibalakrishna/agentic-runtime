"""Scripted turn paths run only where fake models are allowed. Task: M32-T05."""

import uuid

import pytest

import ar_domain.skills.turn as skills_turn
import ar_domain.tools.chat_loop as chat_loop
from ar_domain.chat.service import ChatService, demo_id


def _turn(store: ChatService) -> uuid.UUID:
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "file a ticket about printers",
        schedule=False,
    )
    return uuid.UUID(str(posted["run"]["id"]))


@pytest.mark.asyncio
async def test_scripted_paths_are_skipped_when_fake_models_are_not_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def compose(*_args: object, **_kwargs: object) -> bool:
        calls.append("compose")
        return False

    async def tools(*_args: object, **_kwargs: object) -> bool:
        calls.append("tools")
        return False

    monkeypatch.setattr(skills_turn, "maybe_compose", compose)
    monkeypatch.setattr(chat_loop, "maybe_tools", tools)

    allowed = ChatService()
    await allowed.generate(_turn(allowed), "file a ticket about printers", [])
    assert calls == ["compose", "tools"]

    calls.clear()
    blocked = ChatService()
    blocked.fake_models_allowed = False
    await blocked.generate(_turn(blocked), "file a ticket about printers", [])
    assert calls == []
