"""ReindexCollectionWorkflow on the time-skipping server, with the ingest worker's activities.

The re-index is asked for the way the API asks for it (``KnowledgeBook.reindex_collection``)
and runs on a worker polling the real workflow and activities. Documents are embedded by
the test model server, as everywhere in the unit suite.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from temporalio.worker import Worker

from ar_domain.agents.access import Actor
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.members import add_member
from ar_domain.knowledge.store import memory_index
from ar_ingest.activities import bind_store
from ar_ingest.main import TASK_QUEUE
from ar_ingest.worker import ingest_activities
from ar_ingest.workflows.reindex_collection import BATCH, ReindexCollectionWorkflow
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment

_PAGES = [(f"Page {n}", f"# Page {n}\n\nRoom {n} is on floor {n % 4}.") for n in range(BATCH + 3)]


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)


async def _collection(store: Any) -> uuid.UUID:
    actor = _actor()
    made = KnowledgeBook(store).create_collection(actor, {"name": "Rooms", "slug": "rooms"})
    collection_id = uuid.UUID(str(made["id"]))
    for title, text in _PAGES:
        await add_member(
            store, actor, collection_id, {"kind": "text", "title": title, "text": text}
        )
    return collection_id


def _versions(store: Any, collection_id: uuid.UUID) -> dict[int, int]:
    """How many vectors of the collection each index version holds."""
    counted: dict[int, int] = {}
    for row in memory_index(store).rows.values():  # type: ignore[attr-defined]
        if row.collection_id == collection_id:
            counted[row.index_version] = counted.get(row.index_version, 0) + 1
    return counted


def _passages(store: Any, collection_id: uuid.UUID) -> list[dict[str, Any]]:
    documents = {
        key
        for key, row in store.knowledge_documents.items()
        if row.get("collection_id") == collection_id
    }
    return [row for row in store.document_chunks.values() if row.get("document_id") in documents]


async def _reindex(
    env: WorkflowEnvironment, store: Any, collection_id: uuid.UUID, body: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    store.temporal_client = env.client
    bind_store(store)
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[ReindexCollectionWorkflow],
        activities=ingest_activities(),
    ):
        queued = await KnowledgeBook(store).reindex_collection(_actor(), collection_id, body)
        result = await env.client.get_workflow_handle(f"reindex-{collection_id}").result()
    return store.ingestion_jobs[uuid.UUID(queued["job_id"])], result


async def test_a_reindex_writes_every_document_then_switches_and_drops_the_old_version(
    temporal_env: WorkflowEnvironment,
) -> None:
    store = demo_store()
    collection_id = await _collection(store)
    before = _versions(store, collection_id)
    assert set(before) == {1}

    job, result = await _reindex(
        temporal_env, store, collection_id, {"chunking": {"contextual": True}}
    )

    assert result["status"] == "succeeded"
    assert job["status"] == "succeeded"
    assert job["error"] is None
    # More documents than one batch: every one of them is in the new version.
    assert job["stats"]["seen"] == job["stats"]["updated"] == len(_PAGES)
    collection = store.knowledge_collections[collection_id]
    assert collection["index_version"] == 2
    assert collection["chunking"]["contextual"] is True
    # The old version's vectors and passages are gone; the new one holds every document.
    assert set(_versions(store, collection_id)) == {2}
    passages = _passages(store, collection_id)
    assert {row["index_version"] for row in passages} == {2}
    assert {row["document_id"] for row in passages} == {
        key
        for key, row in store.knowledge_documents.items()
        if row["collection_id"] == collection_id
    }
    # The new passages were built with the settings asked for.
    assert all(row["context_prefix"] for row in passages)
    found = KnowledgeBook(store).search(
        _actor(), {"query": "Which floor is room 3 on?", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "Page 3" for hit in found["hits"])  # type: ignore[union-attr]
    assert any(
        row.get("action") == "collection.reindexed" and row.get("target_id") == str(collection_id)
        for row in store.audit_log
    )


async def test_a_reindex_that_cannot_embed_fails_and_keeps_the_old_version_in_use(
    temporal_env: WorkflowEnvironment,
) -> None:
    store = demo_store()
    collection_id = await _collection(store)
    collection = store.knowledge_collections[collection_id]
    before = _versions(store, collection_id)
    passages = len(_passages(store, collection_id))
    # The model that indexed the collection is gone: no document can be embedded again.
    model = store.models.pop(collection["embedding_model_id"])

    job, result = await _reindex(
        temporal_env, store, collection_id, {"chunking": {"contextual": True}}
    )

    assert result["status"] == "failed"
    assert job["status"] == "failed"
    assert str(job["error"]).startswith("embedding_unconfigured: ")
    assert collection["index_version"] == 1
    assert collection["chunking"]["contextual"] is False
    # What the re-index wrote is removed; the version in use is whole.
    assert _versions(store, collection_id) == before
    assert len(_passages(store, collection_id)) == passages
    assert {row["index_version"] for row in _passages(store, collection_id)} == {1}
    store.models[collection["embedding_model_id"]] = model
    found = KnowledgeBook(store).search(
        _actor(), {"query": "Which floor is room 3 on?", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "Page 3" for hit in found["hits"])  # type: ignore[union-attr]


async def test_a_reindex_with_a_document_it_cannot_read_fails_and_names_it(
    temporal_env: WorkflowEnvironment,
) -> None:
    store = demo_store()
    collection_id = await _collection(store)
    collection = store.knowledge_collections[collection_id]
    before = _versions(store, collection_id)
    lost = next(
        row for row in store.knowledge_documents.values() if row["collection_id"] == collection_id
    )
    # The file the document was made from is gone, so it cannot be read again.
    lost["raw_file_id"] = None

    job, result = await _reindex(temporal_env, store, collection_id, {})

    assert result["status"] == "failed"
    assert "1 document(s) could not be read again" in str(job["error"])
    assert job["stats"]["unreadable"] == [str(lost["id"])]
    assert collection["index_version"] == 1
    assert _versions(store, collection_id) == before
