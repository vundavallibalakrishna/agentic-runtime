"""`:reindex` queues the work on the ingest worker and answers at once.

The request saves a queued job and starts `ReindexCollectionWorkflow`; it reads and embeds
nothing. The collection keeps the settings and the index it is searched with until the
worker has built the new version (docs/03-specs/10-knowledge.md §4.5).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


class _Engine:
    """A workflow engine that records the workflows it is asked to start and runs none."""

    def __init__(self) -> None:
        self.started: list[tuple[object, dict[str, Any], dict[str, Any]]] = []

    async def start_workflow(self, workflow: object, arg: Any, **kwargs: Any) -> None:
        self.started.append((workflow, arg, kwargs))


def _as(app: Any, tenant: uuid.UUID, user: str = "admin") -> TestClient:
    principal = Principal(
        kind="user",
        id=str(demo_id(user)),
        tenant_id=tenant,
        permissions=PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email=f"{user}@dev.local",
        display_name=user,
        roles=frozenset({"tenant_admin"}),
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    client = TestClient(app)
    client.app.state.resolve_principal = resolve  # type: ignore[attr-defined]
    client.app.state.await_runs = True  # type: ignore[attr-defined]
    return client


def _collection_with_a_document(admin: TestClient) -> str:
    created = admin.post(
        "/api/v1/knowledge/collections", json={"slug": "handbook", "name": "Handbook"}
    )
    assert created.status_code == 200
    collection_id = str(created.json()["id"])
    added = admin.post(
        f"/api/v1/knowledge/collections/{collection_id}/members",
        json={"kind": "text", "title": "Desk hours", "text": "The visitor desk opens at 08:30."},
    )
    assert added.status_code == 200
    return collection_id


def _search(admin: TestClient, collection_id: str) -> list[str]:
    found = admin.post(
        "/api/v1/knowledge/search",
        json={"query": "When does the visitor desk open?", "collectionIds": [collection_id]},
    )
    assert found.status_code == 200
    return [hit["title"] for hit in found.json()["hits"]]


def test_a_reindex_is_queued_and_nothing_served_changes_until_it_ends() -> None:
    app = demo_application()
    tenant = demo_id("tenant")
    admin = _as(app, tenant)
    collection_id = _collection_with_a_document(admin)
    before = admin.get(f"/api/v1/knowledge/collections/{collection_id}").json()
    assert "Desk hours" in _search(admin, collection_id)
    engine = _Engine()
    app.state.chat.temporal_client = engine

    began = time.perf_counter()
    queued = admin.post(
        f"/api/v1/knowledge/collections/{collection_id}:reindex",
        json={"chunking": {"contextual": True}, "textSearchConfig": "english"},
    )
    assert queued.status_code == 202
    assert time.perf_counter() - began < 2
    job_id = queued.json()["jobId"]

    # The workflow is started on the ingest worker's queue, once per collection, with the
    # settings the new version is built with.
    [(workflow, payload, options)] = engine.started
    assert workflow == "ReindexCollectionWorkflow"
    assert options == {"id": f"reindex-{collection_id}", "task_queue": "ar-ingest"}
    assert payload["job_id"] == job_id
    assert payload["collection_id"] == collection_id
    assert payload["target"]["chunking"]["contextual"] is True
    assert payload["target"]["text_search_config"] == "english"

    job = admin.get(f"/api/v1/knowledge/jobs/{job_id}").json()
    assert job["kind"] == "reindex"
    assert job["status"] == "queued"
    # The collection is searched as it was: same version, same settings, same answers.
    after = admin.get(f"/api/v1/knowledge/collections/{collection_id}").json()
    assert after["indexVersion"] == before["indexVersion"] == 1
    assert after["embeddingModel"] == before["embeddingModel"]
    row = app.state.chat.knowledge_collections[uuid.UUID(collection_id)]
    assert row["chunking"].get("contextual") is False
    assert row["text_search_config"] == "simple"
    assert "Desk hours" in _search(admin, collection_id)

    # One re-index of a collection at a time.
    again = admin.post(f"/api/v1/knowledge/collections/{collection_id}:reindex", json={})
    assert again.status_code == 409
    assert len(engine.started) == 1


def test_a_reindex_of_another_tenants_collection_is_404() -> None:
    app = demo_application()
    admin = _as(app, demo_id("tenant"))
    collection_id = _collection_with_a_document(admin)
    engine = _Engine()
    app.state.chat.temporal_client = engine
    outsider = _as(app, uuid.uuid4())
    missing = outsider.post(f"/api/v1/knowledge/collections/{collection_id}:reindex", json={})
    assert missing.status_code == 404
    assert engine.started == []
    assert not [
        row for row in app.state.chat.ingestion_jobs.values() if row.get("kind") == "reindex"
    ]


def test_a_reindex_with_no_workflow_engine_says_so_and_queues_nothing() -> None:
    app = demo_application()
    admin = _as(app, demo_id("tenant"))
    collection_id = _collection_with_a_document(admin)
    app.state.chat.temporal_client = None
    refused = admin.post(f"/api/v1/knowledge/collections/{collection_id}:reindex", json={})
    assert refused.status_code == 503
    assert "ingest worker" in refused.text
    assert not [
        row for row in app.state.chat.ingestion_jobs.values() if row.get("kind") == "reindex"
    ]


def test_moving_to_another_vector_store_is_not_a_reindex() -> None:
    app = demo_application()
    admin = _as(app, demo_id("tenant"))
    collection_id = _collection_with_a_document(admin)
    app.state.chat.temporal_client = _Engine()
    refused = admin.post(
        f"/api/v1/knowledge/collections/{collection_id}:reindex",
        json={"targetBackend": "qdrant"},
    )
    assert refused.status_code == 422
