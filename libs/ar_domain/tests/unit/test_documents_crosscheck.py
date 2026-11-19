"""A cross-check reports only disagreements whose quotes are in the document."""

from __future__ import annotations

import uuid
from typing import Any

import orjson
import pytest

from ar_common.errors import ArError
from ar_domain.agents.access import Actor
from ar_domain.documents.crosscheck import CROSSCHECK_BUDGET, crosscheck
from ar_domain.documents.library import DocumentLibrary
from ar_domain.tools.documents import dispatch_documents
from ar_domain.tools.seed_tools import ensure_m33b, shipped_tools
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


def test_a_document_too_long_for_one_pass_is_refused_in_words() -> None:
    document = _document()
    document["passages"] = [
        {"anchor": f"p1-s{index}", "page": 1, "heading": "Part", "text": "word " * 1000}
        for index in range(9)
    ]
    model = _Model(_answer())
    with pytest.raises(ArError) as refused:
        crosscheck(document, model)
    assert refused.value.code.value == "validation_failed"
    assert "too long to check in one pass" in refused.value.detail
    assert str(CROSSCHECK_BUDGET) in refused.value.detail
    assert "Nothing was checked" in refused.value.detail
    # Part of a document is never checked in place of the whole.
    assert model.asked == []


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


def test_the_tool_tells_the_model_to_report_exactly_what_was_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _answer(
        _finding(
            "summary_mismatch",
            ("p1-s0", "| Shelving | Amber |"),
            ("p1-s1", "Grade: Red."),
            statement="Shelving is Amber in the summary and Red in its section.",
        ),
        _finding("value_mismatch", ("p1-s1", "Four of 25 shelves"), ("p1-s1", "Grade: Blue.")),
    )
    store, actor, document_id, model = _library(monkeypatch, reply)
    before = len(store.audit_log)
    result = _call(store, actor, {"documentId": document_id, "focus": "grades"})
    assert result["is_error"] is False
    text = str(result["text"])
    assert "untrusted document data" in text
    assert "1. Shelving is Amber in the summary and Red in its section." in text
    assert '[p1-s0 p.1] "| Shelving | Amber |"' in text
    assert '[p1-s1 p.1] "Grade: Red."' in text
    assert "(1 found, all 3 passages read)" in text
    assert "Report exactly these findings" in text
    assert "Do not add others" in text
    assert "Candidates discarded: 1." in text
    assert "Grade: Blue" not in text
    presentation = result["structured"]["presentation"]  # type: ignore[index]
    assert presentation["kind"] == "crosscheck"
    assert presentation["documentId"] == document_id
    assert len(presentation["findings"]) == 1
    assert len(model.asked) == 3  # the document is read three times
    # A cross-check stores nothing and writes no audit entry: it changes no state.
    assert len(store.audit_log) == before


def test_finding_nothing_says_what_was_read_and_does_not_promise_agreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, actor, document_id, _model = _library(monkeypatch, _answer())
    result = _call(store, actor, {"documentId": document_id})
    assert result["is_error"] is False
    text = str(result["text"])
    assert text.startswith("No disagreement was found between the passages compared.")
    assert "All 3 passages" in text
    assert "not proof" in text
    assert "consistent" not in text.lower()
    presentation = result["structured"]["presentation"]  # type: ignore[index]
    assert presentation["findings"] == []
    assert presentation["passagesRead"] == 3


def test_the_tool_refuses_in_words_when_nothing_could_be_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, actor, document_id, _model = _library(monkeypatch, None)
    silent = _call(store, actor, {"documentId": document_id})
    assert silent["is_error"] is True
    assert silent["code"] == "unavailable"
    assert "was not checked" in str(silent["text"])
    missing = _call(store, actor, {})
    assert missing["code"] == "validation_failed"
    unknown = _call(store, actor, {"documentId": str(uuid.uuid4())})
    assert unknown["code"] == "not_found"
    stranger = Actor(
        tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset({"chat:use"})
    )
    assert _call(store, stranger, {"documentId": document_id})["code"] == "not_found"


def test_comparing_a_document_with_itself_points_at_the_cross_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, actor, document_id, _model = _library(monkeypatch, _answer())
    same = dispatch_documents(
        store,
        "compare",
        {
            "documentId": document_id,
            "otherDocumentId": document_id,
            "_tenant_id": actor.tenant_id,
            "_user_id": actor.user_id,
        },
    )
    assert same["is_error"] is True
    assert "cross-check" in str(same["text"])


def test_the_tool_is_in_a_fresh_catalogue_and_reaches_one_seeded_earlier() -> None:
    shipped = shipped_tools()
    tool = shipped["documents.crosscheck"]
    assert tool["risk_class"] == "R0"
    schema = tool["input_schema"]
    assert isinstance(schema, dict)
    assert schema["required"] == ["documentId"]
    assert set(schema["properties"]) == {"documentId", "focus"}
    description = str(tool["description"])
    assert "agrees with itself" in description
    assert "documents.compare" in description
    assert "documents.judge" in description
    for neighbour in ("documents.compare", "documents.judge"):
        assert "documents.crosscheck" in str(shipped[neighbour]["description"])

    store = demo_store()
    fresh = {str(row.get("qualified_name")) for row in store.tool_versions.values()}
    assert "documents.crosscheck" in fresh
    # An install seeded by an earlier release has the documents server without this tool.
    for bucket in (store.tool_versions, store.tool_defs):
        for key, row in list(bucket.items()):
            if row.get("qualified_name") == "documents.crosscheck":
                del bucket[key]
    server = next(row for row in store.tool_servers.values() if row.get("slug") == "documents")
    version = store.tool_server_versions[server["current_version_id"]]
    version["manifest"] = {
        "tools": [name for name in version["manifest"]["tools"] if name != "crosscheck"]
    }
    ensure_m33b(store)
    added = [
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "documents.crosscheck"
    ]
    assert len(added) == 1
    assert added[0]["tool_server_version_id"] == server["current_version_id"]
    assert "crosscheck" in version["manifest"]["tools"]
    ensure_m33b(store)
    assert (
        sum(
            row.get("qualified_name") == "documents.crosscheck"
            for row in store.tool_versions.values()
        )
        == 1
    )


def test_an_agent_granted_every_documents_tool_is_offered_the_cross_check() -> None:
    from ar_domain.tools.pipeline import ToolPipeline

    store = demo_store()
    names = ToolPipeline(store)._bound("documents", ["*"], uuid.uuid4())
    assert "documents.crosscheck" in {row["qualified_name"] for row in names}


def test_every_parameter_of_the_tool_is_described() -> None:
    schema = shipped_tools()["documents.crosscheck"]["input_schema"]
    assert isinstance(schema, dict)
    for name, body in schema["properties"].items():
        assert str(body.get("description") or "").strip(), name


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
