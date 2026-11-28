"""How many passages a search returns comes from the caller, the agent or the install.

The ``knowledge.search`` tool used 8 whatever the agent's ``knowledge.topK`` said, and the
search endpoint allowed at most 20 whatever ``AR_KNOWLEDGE_SEARCH_MAX_HITS`` said. On a
91-question website check, 8 results found 51% of the expected pages and 16 found 62%.
Proof: unit.
"""

import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from ar_common.settings import get_settings, set_settings
from ar_domain.knowledge.retrieval import result_count

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings as Settings


@pytest.fixture
def settings() -> Iterator[Settings]:
    before = get_settings()
    yield before
    set_settings(before)


def test_the_install_default_is_sixteen_and_a_caller_may_name_its_own() -> None:
    assert result_count() == get_settings().knowledge_top_k == 16
    assert result_count(5) == 5
    assert result_count("many") == 16
    assert result_count(0) == 16
    assert result_count(True) == 16


def test_no_caller_gets_more_than_the_install_allows(settings: Settings) -> None:
    set_settings(settings.model_copy(update={"knowledge_search_max_hits": 12}))
    assert result_count(50) == 12
    assert result_count() == 12


def test_the_default_is_a_setting(settings: Settings) -> None:
    set_settings(settings.model_copy(update={"knowledge_top_k": 6}))
    assert result_count() == 6


class _Store:
    def __init__(self, definition: dict[str, object] | None = None) -> None:
        self.knowledge_documents: dict[object, object] = {}
        self.versions = {"v1": {"definition": definition}} if definition is not None else {}


def _searched(
    monkeypatch: pytest.MonkeyPatch, store: _Store, **arguments: object
) -> dict[str, object]:
    from ar_domain.tools import handlers

    site = uuid.uuid4()
    sent: list[dict[str, object]] = []

    class _Book:
        def __init__(self, store: object) -> None:
            del store

        def list_collections(self, actor: object) -> list[dict[str, object]]:
            del actor
            return [{"id": site, "slug": "site", "name": "Site"}]

        def search(self, actor: object, body: dict[str, object]) -> dict[str, object]:
            del actor
            sent.append(body)
            return {"hits": [], "answerable": False}

    monkeypatch.setattr("ar_domain.knowledge.book.KnowledgeBook", _Book)
    handlers._knowledge(
        store,
        "search",
        {
            "query": "what changed",
            "_tenant_id": uuid.uuid4(),
            "_user_id": uuid.uuid4(),
            **arguments,
        },
    )
    return sent[0]


def test_the_tool_uses_the_install_default_when_nothing_names_a_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _searched(monkeypatch, _Store())["top_k"] == 16


def test_the_tool_uses_the_agents_number_when_the_model_names_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store({"knowledge": {"topK": 5}})
    assert _searched(monkeypatch, store, _agent_version_id="v1")["top_k"] == 5


def test_the_models_own_number_wins_up_to_the_install_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store({"knowledge": {"topK": 5}})
    assert _searched(monkeypatch, store, _agent_version_id="v1", top_k=3)["top_k"] == 3
    assert _searched(monkeypatch, store, _agent_version_id="v1", top_k=99)["top_k"] == 20
