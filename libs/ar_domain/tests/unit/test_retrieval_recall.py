"""Retrieval recall is the share of expected pages that were retrieved."""

from ar_domain.evals.judge import judge_answer
from ar_domain.evals.scoring import summarise
from ar_domain.knowledge.retrieved import retrieval_recall, retrieval_record


def test_a_search_record_keeps_ids_and_not_the_passage_text() -> None:
    record = retrieval_record(
        "desk hours",
        {
            "hits": [
                {
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "uri": "https://example.com/hours",
                    "title": "Hours",
                    "text": "The desk opens at 08:30.",
                    "score": 0.4,
                }
            ]
        },
    )
    assert record is not None
    assert record["query"] == "desk hours"
    passage = record["passages"][0]  # type: ignore[index]
    assert passage["document_id"] == "d1"
    assert passage["rank"] == 1
    assert "text" not in passage
    assert "08:30" not in str(record)


def test_recall_is_the_share_of_expected_pages() -> None:
    passages = [
        {"uri": "https://example.com/hours", "title": "Hours", "document_id": "d1"},
        {"uri": "https://example.com/other", "title": "Other", "document_id": "d2"},
    ]
    measured = retrieval_recall(
        ["https://example.com/hours", "https://example.com/pricing"], passages
    )
    assert measured is not None
    score, found, total = measured
    assert (score, found, total) == (0.5, 1, 2)
    assert retrieval_recall([], passages) is None


def test_a_partial_fact_list_is_weak_and_recall_is_reported_by_category() -> None:
    result = judge_answer(
        "The desk opens at 08:30.",
        ["The desk opens at 08:30.", "Parking is free."],
        [],
        lambda task, evidence: (
            '{"verdict":"stated","quote":"The desk opens at 08:30."}'
            if "08:30" in task
            else '{"verdict":"not_stated","quote":""}'
        ),
        model_id="m1",
    )
    assert result["passed"] is False
    assert result["fact_coverage"] == 0.5
    assert result["grade"] == "weak"
    summary = summarise(
        {},
        [
            {
                "case_id": "a",
                "passed": False,
                "tags": ["hours"],
                "scores": {
                    "llm_judge_0": result,
                    "retrieval_recall": {"score": 0.5, "verdict": "measured"},
                },
                "latency_ms": 1,
                "cost_micros": 0,
            }
        ],
        {},
    )
    assert summary["grades"]["weak"] == 1
    assert summary["fact_coverage"] == 0.5
    assert summary["retrieval_recall"] == 0.5
    assert summary["by_category"]["hours"]["retrieval_recall"] == 0.5
