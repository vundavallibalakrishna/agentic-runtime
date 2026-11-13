"""The browser-test harness resets the demo tenant between a failed attempt and its retry.

The harness keeps one in-memory tenant for a whole run, so a retried flow would otherwise
see the rows the failed attempt left behind. ``rebuild_demo_store`` swaps in a freshly
seeded store so the retry starts from the baseline. Proof: unit.
"""

from ar_domain.chat.service import demo_id
from ar_testing.demo import demo_application, rebuild_demo_store


def test_rebuild_demo_store_drops_attempt_data_and_reseeds() -> None:
    app = demo_application()
    before = app.state.chat
    assert before.agents, "the demo tenant seeds its agents"

    # A row a failed attempt left behind, of the kind a retry would see twice.
    conversation_id = demo_id("left-behind-conversation")
    before.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": demo_id("tenant"),
    }

    rebuild_demo_store(app)

    after = app.state.chat
    assert after is not before, "the store is swapped for a fresh one"
    assert conversation_id not in after.conversations, "the attempt's rows are gone"
    assert after.agents, "the fresh store is seeded again"
    assert app.state.identity_provider is not None, "identity reads from the new store"
