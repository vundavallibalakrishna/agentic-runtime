"""Chat retrieval drops chunks under the configured score."""

from __future__ import annotations

import asyncio
import uuid

from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.members import retrieve
from ar_domain.knowledge.threshold import LIBRARY_MISS
from ar_domain.workspace.turn import citation_parts, ground_run
from ar_testing.demo import demo_store


def test_below_threshold_says_the_library_does_not_contain_the_answer(
    monkeypatch,
) -> None:
    store = demo_store()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    collection_id = uuid.uuid4()
    store.knowledge_collections[collection_id] = {
        "id": collection_id,
        "tenant_id": tenant,
        "slug": "policy",
        "embedding_model": "embed",
    }
    weak = {
        "chunk_id": "c1",
        "document_id": "d1",
        "title": "Policy",
        "text": "The north dock code is ND-1844-QUILL.",
        "snippet": "The north dock code is ND-1844-QUILL.",
        "anchor": "p1",
        "page": 1,
        "similarity": 0.05,
        "rerank_score": 0.05,
    }

    async def search_async(*_args, **_kwargs):
        return {"hits": [weak], "answerable": True, "rerank_model": "rerank"}

    monkeypatch.setattr("ar_domain.knowledge.searching.search_async", search_async)
    actor = Actor(tenant, user, PERMISSION_KEYS)
    found = asyncio.run(
        retrieve(store, actor, [collection_id], "What is the dock code?", min_score=0.8)
    )
    assert found["answerable"] is False
    assert found["hits"] == []
    assert found["answer"] == LIBRARY_MISS
    assert citation_parts(found["trace"]) == []

    version_id = uuid.uuid4()
    run_id = uuid.uuid4()
    store.versions[version_id] = {
        "id": version_id,
        "definition": {
            "instructions": "Answer from the library.",
            "knowledge": {"collections": ["policy"], "min_score": 0.8},
        },
    }
    run = {
        "id": run_id,
        "tenant_id": tenant,
        "user_id": user,
        "agent_version_id": version_id,
        "prompt_messages": [{"role": "system", "content": "Answer from the library."}],
    }
    asyncio.run(ground_run(store, run, "What is the dock code?"))
    system = str(run["prompt_messages"][0]["content"])
    assert "The library does not contain the answer to this question." in system
    assert "ND-1844-QUILL" not in system
    assert citation_parts(run.get("retrieval")) == []
