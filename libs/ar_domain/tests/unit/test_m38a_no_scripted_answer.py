"""No deployed turn produces text a model did not write. Task: M38a-T02c.

Two paths used to answer without a model: the auto-retrieve knowledge answer, which
joined retrieved snippets into prose, and a delegated child, which returned a canned
string. Both now go through the tenant's model; the delegate half is covered by
``test_m9_skills.test_research_lead_merges_two_children_and_cancel_stops_them``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ar_domain.chat.service import demo_id
from ar_domain.knowledge.answer import compose
from ar_testing.demo import demo_store
from ar_testing.demo_tenant import seed_demo
from ar_testing.showcase_build import seed_showcase

if TYPE_CHECKING:
    from ar_testing.stand_in import StandIn

pytestmark = pytest.mark.unit

_MODEL_ANSWER = "The grounded answer the model wrote"


def _librarian_run(store: object) -> dict[str, object]:
    agent = next(row for row in store.agents.values() if row.get("slug") == "librarian")  # type: ignore[attr-defined]
    version = next(
        row
        for row in store.versions.values()  # type: ignore[attr-defined]
        if row.get("agent_id") == agent["id"]
    )
    store.user_roles[demo_id("admin")] = {"tenant_admin"}  # type: ignore[attr-defined]
    return {
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "agent_version_id": version["id"],
    }


@pytest.mark.asyncio
async def test_auto_retrieve_answer_is_written_by_the_model(stand_in: StandIn) -> None:
    store = demo_store(allow_loopback=True)
    seed_demo(store)
    seed_showcase(store)
    stand_in.script(
        "m38a-grounded",
        [{"match": {"contains": "payroll"}, "respond": {"text": f"{_MODEL_ANSWER} [1]."}}],
    )
    stand_in.connect(store, demo_id("tenant"), script_set="m38a-grounded")

    composed = await compose(store, _librarian_run(store), "When is payroll released?")

    assert composed is not None
    assert composed["citations"], "the model answered from retrieved sources"
    assert _MODEL_ANSWER in str(composed["text"])


@pytest.mark.asyncio
async def test_auto_retrieve_refuses_without_a_model() -> None:
    # The demo tenant's only provider is the fake alias, so no real model is connected.
    store = demo_store(allow_loopback=True)
    seed_demo(store)
    seed_showcase(store)

    composed = await compose(store, _librarian_run(store), "When is payroll released?")

    assert composed is not None
    text = str(composed["text"])
    assert "no model connected" in text
    # It never falls back to joining the retrieved snippets into an answer.
    assert _MODEL_ANSWER not in text
