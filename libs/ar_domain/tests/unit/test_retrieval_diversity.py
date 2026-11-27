"""A wide candidate pool, then at most a few passages from each document."""

from ar_domain.knowledge.retrieval import candidate_k, diversify, max_per_document


def test_one_document_cannot_fill_the_selection() -> None:
    hits = [
        {"document_id": "a", "chunk_id": "a1"},
        {"document_id": "a", "chunk_id": "a2"},
        {"document_id": "a", "chunk_id": "a3"},
        {"document_id": "b", "chunk_id": "b1"},
        {"document_id": "c", "chunk_id": "c1"},
    ]
    chosen = diversify(hits, top_k=4, per_document=2)
    assert [hit["chunk_id"] for hit in chosen] == ["a1", "a2", "b1", "c1"]


def test_defaults_are_a_wide_pool_and_two_passages_a_document() -> None:
    assert candidate_k(None) == 60
    assert candidate_k(12) == 12
    assert max_per_document(None) == 2
    assert max_per_document(4) == 4
