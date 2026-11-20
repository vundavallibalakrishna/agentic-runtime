"""A cross-check reports only disagreements whose quotes are in the document."""

from __future__ import annotations

import uuid
from typing import Any

import orjson
import pytest

from ar_common.errors import ArError
from ar_domain.agents.access import Actor
from ar_domain.documents.crosscheck import crosscheck
from ar_domain.documents.library import DocumentLibrary
from ar_domain.tools.documents import dispatch_documents
from ar_testing.demo import demo_store

_REPORT = (
    b"# Stock count\n\n"
    b"## Summary\n\n"
    b"| Item | Grade |\n|---|---|\n| Shelving | Amber |\n| Lighting | Green |\n\n"
    b"Two items were graded: one Red and one Green.\n\n"
    b"## Shelving\n\n"
    b"Grade: Red.\n\n"
    b"Four of 25 shelves were loose. The count covered 30 shelves.\n\n"
    b"## Lighting\n\n"
    b"Grade: Green.\n\n"
    b"All 25 lamps worked.\n"
)


def _document() -> dict[str, object]:
    return {
        "id": "d1",
        "title": "Stock count",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Summary",
                "text": "| Shelving | Amber |\nTwo items were graded: one Red and one Green.",
            },
            {
                "anchor": "p1-s1",
                "page": 1,
                "heading": "Shelving",
                "text": "Grade: Red.\nFour of 25 shelves were loose. The count covered 30 shelves.",
            },
        ],
    }


def _answer(*findings: object) -> str:
    return orjson.dumps({"findings": list(findings)}).decode()


def _finding(kind: str, *quotes: tuple[str, ...], statement: str = "") -> dict[str, object]:
    return {
        "statement": statement or "The two places give different values.",
        "kind": kind,
        # The value each place gives is the whole quote unless a test names it.
        "quotes": [
            {"anchor": row[0], "quote": row[1], "value": row[2] if len(row) > 2 else row[1]}
            for row in quotes
        ],
    }


def _found(result: dict[str, object]) -> list[dict[str, Any]]:
    findings = result["findings"]
    assert isinstance(findings, list)
    return findings


class _Model:
    """Answers every question with one prepared reply and keeps what it was asked."""

    def __init__(self, reply: str | None) -> None:
        self.reply = reply
        self.asked: list[tuple[str, str]] = []

    def __call__(self, task: str, evidence: str) -> str | None:
        self.asked.append((task, evidence))
        return self.reply


def test_a_finding_with_quotes_from_the_document_is_returned_with_its_anchors() -> None:
    model = _Model(
        _answer(
            _finding(
                "summary_mismatch",
                ("p1-s0", "| Shelving | Amber |"),
                ("p1-s1", "Grade:  red."),
                statement="Shelving is Amber in the summary and Red in its section.",
            ),
            _finding(
                "value_mismatch",
                ("p1-s1", "Four of 25 shelves"),
                ("p1-s1", "The count covered 30 shelves"),
            ),
        )
    )
    result = crosscheck(_document(), model, focus="  grades\nand counts ")
    assert result["kind"] == "crosscheck"
    assert result["passagesRead"] == 2
    assert result["discarded"] == 0
    assert result["focus"] == "grades and counts"
    first, second = _found(result)
    assert first["kind"] == "summary_mismatch"
    assert first["statement"] == "Shelving is Amber in the summary and Red in its section."
    # Spacing and capitals differ between a passage and a model's copy of it.
    assert [row["anchor"] for row in first["quotes"]] == ["p1-s0", "p1-s1"]
    assert first["quotes"][0]["page"] == 1
    assert [row["anchor"] for row in second["quotes"]] == ["p1-s1", "p1-s1"]
    task, evidence = model.asked[0]
    # The whole document is sent, each passage wrapped as untrusted text.
    assert evidence.count("<untrusted_content") == 2
    assert "anchor: p1-s0" in evidence
    assert "anchor: p1-s1" in evidence
    assert "Pay most attention to: grades and counts" in task


def test_a_finding_whose_quote_is_not_in_the_document_is_dropped() -> None:
    model = _Model(
        _answer(
            _finding("value_mismatch", ("p1-s0", "| Shelving | Amber |"), ("p1-s1", "Grade: Blue")),
            _finding("other", ("p1-s9", "Grade: Red."), ("p1-s0", "| Shelving | Amber |")),
            # The words are in the document, but not in the passage the model named.
            _finding("other", ("p1-s0", "Grade: Red."), ("p1-s0", "| Shelving | Amber |")),
        )
    )
    result = crosscheck(_document(), model)
    assert result["findings"] == []
    assert result["discarded"] == 3


def test_quotes_that_say_the_same_thing_are_dropped() -> None:
    model = _Model(
        _answer(
            _finding("other", ("p1-s1", "Grade: Red."), ("p1-s1", "grade:  red.")),
            _finding("other", ("p1-s0", "one Red"), ("p1-s1", "Red")),
            _finding("other", ("p1-s0", "one Green"), ("p1-s1", "Red")),
            _finding(
                "value_mismatch",
                ("p1-s1", "Four of 25 shelves"),
                ("p1-s1", "25 shelves were loose"),
            ),
            _finding("value_mismatch", ("p1-s1", "Four of 25 shelves")),
            {"statement": "", "kind": "other", "quotes": []},
            "not a finding",
        )
    )
    result = crosscheck(_document(), model)
    findings = _found(result)
    # Different words in two places stay: only a person or the model can weigh them. A
    # value whose words are all in the other ("one Red" beside "Red") is the same value.
    assert [row["quotes"][0]["quote"] for row in findings] == ["one Green"]
    assert result["discarded"] == 6


def test_an_unknown_kind_is_kept_as_other() -> None:
    model = _Model(
        _answer(_finding("made_up", ("p1-s0", "one Red"), ("p1-s0", "| Shelving | Amber |")))
    )
    assert _found(crosscheck(_document(), model))[0]["kind"] == "other"


def test_a_table_kept_apart_from_the_passages_is_read_too() -> None:
    document = _document()
    document["tables"] = [
        {"anchor": "t1", "page": 1, "caption": "Grades", "csv": "Item,Grade\nShelving,Amber\n"}
    ]
    model = _Model(
        _answer(_finding("summary_mismatch", ("t1", "Shelving,Amber"), ("p1-s1", "Grade: Red.")))
    )
    result = crosscheck(document, model)
    assert result["passagesRead"] == 3
    assert [row["anchor"] for row in _found(result)[0]["quotes"]] == ["t1", "p1-s1"]
    assert "anchor: t1" in model.asked[0][1]


def test_a_document_too_long_for_one_pass_is_read_in_sections() -> None:
    document = _document()
    document["passages"] = [
        {"anchor": f"p1-s{index}", "page": 1, "heading": "Part", "text": "word " * 1000}
        for index in range(9)
    ]
    model = _Model(_answer())
    result = crosscheck(document, model)
    assert result["sectioned"] is True
    assert result["passagesRead"] == 9
    assert result["findings"] == []
    assert model.asked


def test_no_answer_is_an_error_and_never_a_clean_result() -> None:
    for reply in (None, "I could not find anything.", '{"claims": []}'):
        with pytest.raises(ArError) as failed:
            crosscheck(_document(), _Model(reply))
        assert failed.value.code.value == "unavailable"
        assert "was not checked" in failed.value.detail
    with pytest.raises(ArError):
        crosscheck({"id": "empty", "passages": []}, _Model(_answer()))


def test_the_masked_text_goes_to_the_model_and_the_stored_text_checks_the_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown: list[bool] = []

    def prepare(text: str, *, aggressive: bool) -> str:
        shown.append(aggressive)
        return text.replace("Red", "[MASKED]") if aggressive else text

    monkeypatch.setattr("ar_domain.documents.grounding.prepare_analysis_text", prepare)
    model = _Model(
        _answer(_finding("other", ("p1-s0", "| Shelving | Amber |"), ("p1-s1", "Grade: [MASKED].")))
    )
    result = crosscheck(_document(), model, aggressive=True)
    assert shown == [True, True]
    assert "Grade: [MASKED]." in model.asked[0][1]
    assert result["findings"] == []
    assert result["discarded"] == 1


def _library(monkeypatch: pytest.MonkeyPatch, reply: str | None) -> tuple[Any, Actor, str, _Model]:
    """A store with one ingested report, and the model the library will ask."""
    store = demo_store()
    actor = Actor(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset({"chat:use"}))
    saved = DocumentLibrary(store).ingest(actor, data=_REPORT, filename="stock.md")
    model = _Model(reply)
    monkeypatch.setattr(DocumentLibrary, "_ask", lambda _self, _actor, _alias: model)
    return store, actor, str(saved["id"]), model


def _call(store: Any, actor: Actor, arguments: dict[str, object]) -> dict[str, object]:
    return dispatch_documents(
        store,
        "crosscheck",
        {**arguments, "_tenant_id": actor.tenant_id, "_user_id": actor.user_id},
    )


def test_places_that_give_the_same_value_are_not_a_finding() -> None:
    answer = _answer(
        _finding(
            "value_mismatch",
            ("p1-s0", "one Red and one Green", "Red"),
            ("p1-s1", "Grade: Red.", "Red"),
            statement="The summary says one Red and the section is graded Red.",
        ),
        _finding(
            "value_mismatch",
            ("p1-s0", "| Shelving | Amber |", "Amber"),
            ("p1-s1", "Grade: Red.", "Green"),
        ),
    )
    result = crosscheck(_document(), lambda _task, _evidence: answer)
    assert _found(result) == []
    assert result["discarded"] == 2


def test_what_any_reading_finds_is_kept_and_reported_once() -> None:
    real = _finding(
        "value_mismatch",
        ("p1-s0", "| Shelving | Amber |", "Amber"),
        ("p1-s1", "Grade: Red.", "Red"),
    )
    reworded = {**real, "statement": "The table and the section grade shelving differently."}
    answers = iter([_answer(), _answer(real), _answer(reworded)])
    result = crosscheck(_document(), lambda _task, _evidence: next(answers))
    found = _found(result)
    assert len(found) == 1
    assert [row["value"] for row in found[0]["quotes"]] == ["Amber", "Red"]


def test_a_rating_said_with_a_count_agrees_with_the_same_rating() -> None:
    answer = _answer(
        _finding(
            "summary_mismatch",
            ("p1-s0", "one Red and one Green", "one Red"),
            ("p1-s1", "Grade: Red.", "Red"),
        ),
        _finding(
            "count_mismatch",
            ("p1-s1", "Four of 25 shelves were loose.", "25"),
            ("p1-s1", "The count covered 30 shelves.", "30 shelves"),
        ),
    )
    result = crosscheck(_document(), lambda _task, _evidence: answer)
    found = _found(result)
    assert [row["value"] for row in found[0]["quotes"]] == ["25", "30 shelves"]
    assert len(found) == 1
