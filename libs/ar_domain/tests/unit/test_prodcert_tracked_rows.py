"""Production-cert defect 4: rows filled in after assignment must reach the store.

The production store wraps a plain dict into a new ``TrackedRow`` copy on assignment,
so code that stores a dict and then keeps writing to its own variable loses those
writes. The in-memory test store keeps the original object, so these only fail under
tracking — which these tests install. The fix idiom is ``keep``. Proof: unit.
"""

import uuid

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.durable.tracking import install_tracking, keep
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.skills.delegate import _insert_child
from ar_testing.demo import demo_store


def test_keep_persists_writes_a_raw_assignment_would_lose() -> None:
    store = demo_store()
    install_tracking(store)

    # Raw assignment: the tracked bucket stores a copy, so a later write to the
    # original variable is lost — this is the production hazard the defect names.
    raw_key = demo_id("agent-raw")
    original = {"id": raw_key, "slug": "before"}
    store.agents[raw_key] = original
    original["slug"] = "after"
    assert store.agents[raw_key]["slug"] == "before"

    # keep() returns the stored row, so a later write lands where the flush reads it.
    kept_key = demo_id("agent-kept")
    kept = keep(store.agents, kept_key, {"id": kept_key, "slug": "before"})
    kept["slug"] = "after"
    assert store.agents[kept_key]["slug"] == "after"


def test_delegate_insert_child_returns_the_stored_run() -> None:
    store = demo_store()
    install_tracking(store)
    parent = {
        "id": demo_id("parent-run"),
        "tenant_id": demo_id("tenant"),
        "conversation_id": demo_id("conv"),
        "user_id": demo_id("admin"),
        "depth": 0,
        "root_run_id": demo_id("parent-run"),
    }

    child = _insert_child(store, parent, {}, {"agent": "no-such-agent", "task": "do the thing"})
    child_id = child["id"]
    # The delegate flow keeps writing to the returned child as the subagent runs.
    child["status"] = "completed"
    child["result_summary"] = "done"
    child["usage"] = {"tokens_in": 5, "tokens_out": 7}

    stored = store.runs[child_id]
    assert stored["status"] == "completed"
    assert stored["result_summary"] == "done"
    assert stored["usage"]["tokens_out"] == 7


def test_create_source_persists_the_first_sync_state() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    admin = Actor(tenant, demo_id("admin"), PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    store.user_emails[admin.user_id] = "admin@dev.local"
    store.company_domains = {"dev.local"}
    book = KnowledgeBook(store)
    created = book.create_collection(admin, {"slug": "library", "name": "Library"})
    collection_id = uuid.UUID(str(created["id"]))

    install_tracking(store)
    source = book.create_source(
        admin,
        collection_id,
        {
            "name": "SharePoint",
            "kind": "sharepoint",
            "config": {
                "items": [
                    {
                        "external_id": "guide",
                        "title": "Visitor guide",
                        "uri": "sharepoint://guide",
                        "text": "The visitor desk opens at 08:30.",
                        "acl": [{"type": "anyone"}],
                    }
                ]
            },
        },
    )
    source_id = uuid.UUID(str(source["id"]))

    # The first full sync writes the cursor and sync state onto the stored row.
    stored = store.knowledge_sources[source_id]
    assert stored["last_sync_status"] == "succeeded"
    assert stored["last_sync_at"] is not None
    assert stored["cursor"] == {"page": 1}
