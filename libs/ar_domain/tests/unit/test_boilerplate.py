"""Repeated blocks are dropped from a collection. A block that is not repeated stays."""

from ar_domain.knowledge.boilerplate import normalize_block, repeated_keys, without_repeated

_BANNER = "This site uses cookies. Accept all cookies to continue browsing the pages."
_BODY = "The visitor desk opens at 08:30 on weekdays."


def test_a_block_in_most_documents_is_dropped_and_counted() -> None:
    documents = [
        [_BANNER, "Page one has its own hours."],
        [_BANNER, "Page two lists the rooms."],
        [_BANNER, _BODY],
        ["Page four is only about parking and says nothing else here."],
    ]
    repeated = repeated_keys(documents, share=0.3, min_chars=40)
    assert normalize_block(_BANNER) in repeated
    assert normalize_block(_BODY) not in repeated
    kept, dropped = without_repeated(f"{_BANNER}\n\n{_BODY}", repeated, min_chars=40)
    assert dropped == 1
    assert _BODY in kept
    assert "cookies" not in kept


def test_one_document_and_a_short_block_drop_nothing() -> None:
    assert repeated_keys([[_BANNER, _BANNER]], share=0.3, min_chars=40) == set()
    assert repeated_keys([["Hi"], ["Hi"]], share=0.3, min_chars=40) == set()
    assert repeated_keys([[_BANNER], [_BANNER]], share=0, min_chars=40) == set()


def test_the_same_block_is_counted_once_per_document() -> None:
    documents = [[_BANNER, _BANNER], [_BODY]]
    assert repeated_keys(documents, share=0.5, min_chars=40) == set()
