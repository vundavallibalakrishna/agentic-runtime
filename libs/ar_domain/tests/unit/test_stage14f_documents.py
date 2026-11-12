"""Document flows found by a live end-to-end run: long tool results, extraction, anchors.

Proof: unit.
"""

from __future__ import annotations

import uuid

import pytest

from ar_common.errors import ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.documents.grounding import extract_fields
from ar_domain.documents.library import DocumentLibrary
from ar_domain.loop.context import context_limits, fit_messages, has_shortened, read_part
from ar_domain.research.handlers import dispatch_context
from ar_domain.tools.agent_loop import _offer_retrieve
from ar_testing.demo import demo_store

_POLICY = {
    "id": "doc-1",
    "passages": [
        {
            "anchor": "p1-s0",
            "page": 1,
            "heading": "Policy",
            "text": "Version 1.0. Owner: Security.",
        },
        {
            "anchor": "p1-s1",
            "page": 1,
            "heading": "Logging",
            "text": "4.2 Security logs are retained for 365 days.",
        },
    ],
}


def _fit(text: str, tokens: int) -> tuple[str, dict[str, object]]:
    retained: dict[str, object] = {}
    messages, _note = fit_messages(
        [{"role": "tool", "content": text}],
        max_tokens=1_000_000,
        retained=retained,
        tool_result_max_tokens=tokens,
        threshold=0.7,
    )
    return str(messages[0]["content"]), retained


def test_a_tool_result_within_the_agents_setting_reaches_the_model_whole() -> None:
    text = "clause " * 500
    shown, retained = _fit(text, context_limits({})["tool_result_max_tokens"].__int__())
    assert shown == text
    assert not retained.get("outputs")


def test_the_agents_own_setting_decides_where_a_result_is_shortened() -> None:
    limits = context_limits({"context": {"tool_result_max_tokens": 100}})
    assert limits["tool_result_max_tokens"] == 100
    assert context_limits({"context": {"tool_result_max_tokens": "many"}}) == context_limits({})
    shown, retained = _fit("x" * 2000, 100)
    assert len(shown) <= 100 * 4
    assert "context.retrieve" in shown
    assert "offset=" in shown
    assert retained["outputs"]


def test_a_shortened_result_is_read_to_its_end_a_part_at_a_time() -> None:
    full = "".join(f"line {index}\n" for index in range(400))
    shown, retained = _fit(full, 100)
    run: dict[str, object] = {"checkpoint": {"context": retained}}
    output_id = shown.split("output_id=", 1)[1].split(" ", 1)[0]
    offset = int(shown.rsplit("offset=", 1)[1].split(" ", 1)[0])
    joined = full[:offset]
    while True:
        part = read_part(run, output_id, offset)
        assert part is not None
        text = str(part["text"])
        # Each part fits the prompt whole, so reading on never shortens again.
        assert len(text) <= 100 * 4
        following = part["next_offset"]
        joined += text.split("\n[shortened:", 1)[0] if following is not None else text
        if not isinstance(following, int):
            break
        offset = following
    assert joined == full
    assert read_part(run, "missing", 0) is None


def test_the_retrieve_tool_is_offered_once_a_result_was_shortened() -> None:
    store = demo_store()
    run: dict[str, object] = {"id": uuid.uuid4()}
    by_name: dict[str, dict[str, object]] = {}
    tools: list[dict[str, object]] = []
    offered: set[str] = set()
    _offer_retrieve(store, run, by_name, tools, offered)
    assert tools == []
    _shown, retained = _fit("y" * 2000, 100)
    run["checkpoint"] = {"context": retained}
    assert has_shortened(run)
    _offer_retrieve(store, run, by_name, tools, offered)
    _offer_retrieve(store, run, by_name, tools, offered)
    assert len(tools) == 1
    assert "context.retrieve" in by_name
    store.runs[run["id"]] = run
    output_id = next(iter(retained["outputs"]))  # type: ignore[call-overload]
    answer = dispatch_context(
        store, "retrieve", {"output_id": output_id, "offset": 0, "_run_id": run["id"]}
    )
    assert answer["is_error"] is False
    assert str(answer["text"]).startswith("y")
    assert answer["structured"]["next_offset"]  # type: ignore[index]


def test_extraction_does_not_guess_a_value_from_a_nearby_passage() -> None:
    result = extract_fields(_POLICY, ["log retention period", "version"], None)
    by_field = {row["field"]: row for row in result["fields"]}  # type: ignore[index, union-attr]
    assert by_field["log retention period"]["value"] is None
    assert by_field["log retention period"]["citation"] is None
    assert by_field["version"]["value"] is None


def test_extraction_keeps_a_labelled_value_without_a_model() -> None:
    result = extract_fields(_POLICY, ["owner"], None)
    row = result["fields"][0]  # type: ignore[index]
    assert row["value"] == "Security."
    assert row["citation"]["anchor"] == "p1-s0"


def test_extraction_reads_a_value_worded_differently_from_the_field_name() -> None:
    def ask(_system: str, evidence: str) -> str:
        assert "retained for 365 days" in evidence
        return (
            '{"value": "365 days", "quote": "Security logs are retained for 365 days.", '
            '"anchor": "p1-s1"}'
        )

    row = extract_fields(_POLICY, ["log retention period"], ask)["fields"][0]  # type: ignore[index]
    assert row["value"] == "365 days"
    assert row["citation"]["anchor"] == "p1-s1"
    assert row["citation"]["quote"] == "Security logs are retained for 365 days."


def test_extraction_refuses_a_value_the_document_does_not_state() -> None:
    def ask(_system: str, _evidence: str) -> str:
        return '{"value": "90 days", "quote": "Logs are kept for 90 days.", "anchor": "p1-s1"}'

    row = extract_fields(_POLICY, ["log retention period"], ask)["fields"][0]  # type: ignore[index]
    assert row["value"] is None
    assert row["confidence"] == 0


def test_reading_an_anchor_the_document_does_not_have_says_so() -> None:
    store = demo_store()
    library = DocumentLibrary(store)
    actor = Actor(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset({"chat:use"}))
    saved = library.ingest(
        actor, data=b"# Access\n\nStaff use badges at the door.", filename="a.md"
    )
    document_id = uuid.UUID(str(saved["id"]))
    with pytest.raises(ValidationFailedError) as raised:
        library.read(actor, document_id, anchor="p1-2")
    assert "no anchor 'p1-2'" in raised.value.detail
    assert "without an anchor" in raised.value.detail
    assert "badges" in str(library.read(actor, document_id)["text"])


def test_a_comparison_names_which_document_is_left_and_which_is_right() -> None:
    from ar_domain.tools.documents import _change_text

    text = _change_text(
        {
            "left_title": "vendor-draft.md",
            "right_title": "our-standard.md",
            "changes": [
                {"op": "added", "heading": "9. Audit", "right_anchor": "p1-s8", "after": "Audits."}
            ],
        }
    )
    assert "Left and before are vendor-draft.md" in text
    assert "Right and after are our-standard.md" in text
    assert "An added passage is only in the right" in text
    assert "added 9. Audit" in text


def test_the_model_reads_the_whole_tool_result_not_the_screen_preview() -> None:
    from ar_domain.tools.agent_loop import _model_text

    whole = "<tool_result>" + "clause " * 1000 + "the last clause</tool_result>"
    result: dict[str, object] = {"wrapped": whole, "result_preview": whole[:2047] + "…"}
    assert _model_text(result, "documents.compare", "c1", "short", failed=False) == whole
    failed = _model_text(result, "documents.compare", "c1", "It did not run.", failed=True)
    assert "It did not run." in failed
    assert "the last clause" not in failed
    bare = _model_text({}, "documents.compare", "c1", "", failed=False)
    assert "empty" in bare


def test_a_markdown_document_is_named_by_its_first_heading() -> None:
    from ar_domain.documents.extract import extract_bytes

    titled = extract_bytes(
        b"# Vendor addendum\n\n## 1. Scope\nThe vendor processes data.\n", filename="draft.md"
    )
    assert titled.title == "Vendor addendum"
    plain = extract_bytes(b"No heading here, only text.\n", filename="note.md")
    assert plain.title == "note"
