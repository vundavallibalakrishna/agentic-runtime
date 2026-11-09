"""knowledge.search resolves a collection the model named, and never crashes on a bad id.

The model only sees a collection's name in its context, so it often passes a name (or a
slug, or a hallucinated id) where a uuid is expected. The tool handler must resolve any of
those and drop what it cannot, so the search falls back to every readable collection rather
than crashing with "badly formed hexadecimal UUID string".
"""

import uuid

from ar_domain.tools.handlers import _resolve_collection_ids


def _collection(name: str, slug: str) -> dict[str, object]:
    return {"id": str(uuid.uuid4()), "name": name, "slug": slug}


def test_resolves_a_uuid_a_slug_or_a_name_and_drops_the_rest() -> None:
    trust = _collection("ACME Trust Library", "acme-trust-library")
    policies = _collection("Policies", "policies")
    collections = [trust, policies]

    # A real uuid of a readable collection.
    assert _resolve_collection_ids([trust["id"]], collections) == [trust["id"]]
    # A slug.
    assert _resolve_collection_ids(["acme-trust-library"], collections) == [trust["id"]]
    # A name, case-insensitive — what the model most often passes.
    assert _resolve_collection_ids(["acme trust library"], collections) == [trust["id"]]
    # A hallucinated name or an id the person cannot read resolves to nothing, so the
    # handler then searches every readable collection instead of crashing.
    assert _resolve_collection_ids(["ACME trust library (v2)"], collections) == []
    assert _resolve_collection_ids([str(uuid.uuid4())], collections) == []
    assert _resolve_collection_ids(["not a uuid at all"], collections) == []
    # A mix keeps the ones that resolve, in order, without duplicates.
    assert _resolve_collection_ids(
        [trust["id"], "ACME Trust Library", "garbage", policies["slug"], trust["slug"]],
        collections,
    ) == [trust["id"], policies["id"]]
    # Anything that is not a list is ignored.
    assert _resolve_collection_ids("acme-trust-library", collections) == []
    assert _resolve_collection_ids(None, collections) == []
