"""The builder drafts with the reasoning model and repairs once. Task: M32-T06."""

import uuid

import httpx
import orjson
import pytest

from ar_common.errors import ArError
from ar_domain.agents.access import Actor
from ar_domain.agents.assist import draft_from_description
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_store

GOOD = {
    "persona": {"display_name": "Vendor reviewer", "greeting": "Send me the report."},
    "instructions": "Review vendor reports and list the gaps with evidence.",
    "starter_prompts": ["Review this report", "What is missing?"],
    "model": {"alias": "reasoning"},
    "tools": [{"server": "files", "version": "*", "include": ["*"]}],
}


def _actor() -> Actor:
    return Actor(tenant_id=demo_id("tenant"), user_id=demo_id("admin"), permissions=PERMISSION_KEYS)


def _real_store() -> ChatService:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
    return store


def _responses(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> list[dict[str, object]]:
    """Answer each chat completion from ``answers`` and record the request bodies."""
    seen: list[dict[str, object]] = []

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(
            self, _url: str, *, json: dict[str, object], headers: object
        ) -> httpx.Response:
            del headers
            seen.append(json)
            text = answers.pop(0)
            return httpx.Response(
                200, json={"choices": [{"message": {"role": "assistant", "content": text}}]}
            )

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return seen


@pytest.mark.asyncio
async def test_model_draft_is_used_when_a_real_model_is_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _real_store()
    seen = _responses(monkeypatch, [orjson.dumps(GOOD).decode()])
    drafted = await draft_from_description(store, _actor(), "Review vendor reports for gaps")
    assert drafted["definition"]["persona"]["displayName"] == "Vendor reviewer"
    assert "reasoning model" in drafted["rationale"]
    assert len(seen) == 1
    system = str(seen[0]["messages"][0]["content"])
    assert "JSON" in system
    assert "files" in system, "the prompt lists the tool servers the model may use"


@pytest.mark.asyncio
async def test_invalid_model_draft_is_repaired_once_with_the_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _real_store()
    bad = dict(GOOD, persona={"display_name": "x" * 120, "greeting": "Hi"})
    seen = _responses(monkeypatch, [orjson.dumps(bad).decode(), orjson.dumps(GOOD).decode()])
    drafted = await draft_from_description(store, _actor(), "Review vendor reports for gaps")
    assert drafted["definition"]["persona"]["displayName"] == "Vendor reviewer"
    assert len(seen) == 2
    repair = str(seen[1]["messages"][1]["content"])
    assert "failed validation" in repair
    assert "display_name" in repair or "displayName" in repair


@pytest.mark.asyncio
async def test_scripted_proposal_is_the_last_resort(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _real_store()
    seen = _responses(monkeypatch, ["not json", "still not json"])
    drafted = await draft_from_description(store, _actor(), "Summarise weekly status notes")
    assert len(seen) == 2
    assert drafted["rationale"].startswith("Drafted a persona")
    assert drafted["definition"]["persona"]["displayName"] == "Summarise weekly status notes"


@pytest.mark.asyncio
async def test_fake_model_never_calls_a_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    seen = _responses(monkeypatch, [])
    drafted = await draft_from_description(store, _actor(), "Answer HR questions")
    assert seen == []
    assert drafted["rationale"].startswith("Drafted a persona")


@pytest.mark.asyncio
async def test_strict_mode_still_fails_without_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _real_store()
    store.builder_strict = True
    _responses(monkeypatch, ["nope"])
    with pytest.raises(ArError):
        await draft_from_description(store, _actor(), "Anything")
    assert uuid.UUID(str(demo_id("tenant")))
