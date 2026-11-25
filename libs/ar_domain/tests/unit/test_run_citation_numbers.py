"""Knowledge passages are numbered once per run, and an answer's cards are the ones it cites."""

from ar_domain.knowledge.members import number_found
from ar_domain.tools.agent_loop import _found_text, _with_trace
from ar_domain.workspace.turn import citation_parts


def _hit(chunk: str, title: str, uri: str, text: str = "Passage text.") -> dict[str, object]:
    return {
        "chunk_id": chunk,
        "document_id": f"doc-{chunk}",
        "title": title,
        "uri": uri,
        "snippet": text,
        "text": text,
        "anchor": "",
    }


def _run_with_prompt_passages() -> dict[str, object]:
    run: dict[str, object] = {"id": "r1"}
    number_found(
        run,
        [
            _hit("a", "Continuity", "https://example.test/bcm/"),
            _hit("b", "Incidents", "https://example.test/incidents/"),
        ],
    )
    return run


def test_a_passage_found_later_is_numbered_after_the_prompt_passages() -> None:
    run = _run_with_prompt_passages()

    numbers = number_found(
        run,
        [
            _hit("b", "Incidents", "https://example.test/incidents/"),
            _hit("c", "Industries", "https://example.test/industries/"),
        ],
    )

    assert numbers == [2, 3]  # one already held keeps its number, a new one comes after
    held = run["retrieval"]["hits"]  # type: ignore[index]
    assert [row["chunk_id"] for row in held] == ["a", "b", "c"]


def test_the_model_reads_found_passages_under_their_run_numbers_and_wrapped() -> None:
    run = _run_with_prompt_passages()
    found = {
        "hits": [
            _hit(
                "c",
                "Industries",
                "https://example.test/industries/",
                "Banking, insurance and mining.",
            )
        ],
        "answerable": True,
    }

    text = _found_text(run, found, "knowledge.search", "call-1")

    assert text is not None
    assert 'trust="untrusted"' in text
    assert "[3] Industries (https://example.test/industries/)" in text
    assert "Banking, insurance and mining." in text
    assert "[1]" not in text


def test_a_search_that_found_nothing_leaves_the_gateway_text() -> None:
    assert (
        _found_text({"id": "r"}, {"hits": [], "answerable": False}, "knowledge.search", "c") is None
    )


def test_the_cards_are_the_passages_the_answer_cites() -> None:
    run = _run_with_prompt_passages()
    _found_text(
        run,
        {"hits": [_hit("c", "Industries", "https://example.test/industries/")]},
        "knowledge.search",
        "call-1",
    )

    parts = _with_trace(object(), "Banks are covered [3], and so are incidents [2].", run)

    cards = [part["citation"] for part in parts if part["type"] == "citation_ref"]
    assert [(card["index"], card["uri"]) for card in cards] == [
        (2, "https://example.test/incidents/"),
        (3, "https://example.test/industries/"),
    ]


def test_an_answer_that_cites_nothing_still_shows_its_sources() -> None:
    run = _run_with_prompt_passages()

    cards = citation_parts(run["retrieval"], "No markers here.")

    assert [card["index"] for card in cards] == [1, 2]
