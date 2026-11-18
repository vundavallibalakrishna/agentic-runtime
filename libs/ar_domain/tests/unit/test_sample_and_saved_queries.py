"""Sampling a table, saved queries with versions, and sign-off before a run. Proof: unit."""

from __future__ import annotations

import csv
import importlib
import io
import random
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from ar_domain.agents.access import Actor
from ar_domain.agents.logic import assistant_definition, definition_hash
from ar_domain.approvals.reviews import ReviewBook
from ar_domain.durability.store import read_blob
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.spreadsheet.saved import SETTING, SavedQueryBook
from ar_domain.tools.general import _prepare, dispatch_general
from ar_domain.tools.seed_tools import shipped_tools
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_NEW_TOOLS = {"sample_table", "save_query", "list_saved_queries", "run_saved_query"}


def _args() -> tuple[ChatService, dict[str, object]]:
    store = demo_store()
    arguments: dict[str, object] = {
        "_run_id": uuid.uuid4(),
        "_tenant_id": uuid.uuid4(),
        "_user_id": uuid.uuid4(),
    }
    return store, arguments


def _table(store: ChatService, arguments: dict[str, object], name: str, text: str) -> None:
    root = _prepare(store, arguments)
    (root / "workspace" / "inputs" / name).write_text(text, encoding="utf-8")


def _items(count: int) -> str:
    lines = ["id,region,amount"]
    for number in range(1, count + 1):
        region = ("north", "south", "east")[number % 3]
        lines.append(f"{number},{region},{number * 10}")
    return "\n".join(lines) + "\n"


def _presentation(result: dict[str, object]) -> dict[str, object]:
    structured = result["structured"]
    assert isinstance(structured, dict)
    presentation = structured["presentation"]
    assert isinstance(presentation, dict)
    return presentation


def _structured(result: dict[str, object]) -> dict[str, object]:
    structured = result.get("structured") or {}
    assert isinstance(structured, dict)
    presentation = structured.get("presentation") or {}
    assert isinstance(presentation, dict)
    return presentation


def _written(store: ChatService, result: dict[str, object]) -> list[dict[str, str]]:
    files = _presentation(result)["files"]
    assert isinstance(files, list)
    blob = read_blob(store, uuid.UUID(str(files[0]["file_id"])))
    assert blob is not None
    return list(csv.DictReader(io.StringIO(bytes(blob).decode())))


def test_a_random_sample_is_the_same_for_the_same_seed() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(60))
    call = {**arguments, "path": "items.csv", "method": "random", "size": 7, "seed": 11}
    first = dispatch_general(store, "sample_table", dict(call))
    again = dispatch_general(store, "sample_table", dict(call))
    other = dispatch_general(store, "sample_table", {**call, "seed": 12})
    assert first["is_error"] is False
    rows = _written(store, first)
    assert len(rows) == 7
    assert [row["id"] for row in rows] == [row["id"] for row in _written(store, again)]
    assert [row["id"] for row in rows] != [row["id"] for row in _written(store, other)]
    assert {row["selection"] for row in rows} == {"sampled"}
    # The rows are the ones Python's seeded generator picks over the file order.
    expected = sorted(random.Random(11).sample(range(60), 7))  # noqa: S311
    assert [int(row["id"]) for row in rows] == [index + 1 for index in expected]
    summary = _presentation(first)["sample"]
    assert isinstance(summary, dict)
    assert summary["seed"] == 11
    assert summary["population_rows"] == 60
    assert summary["sampled_rows"] == 7
    assert "Seed: 11" in str(first["text"])
    assert _presentation(first)["kind"] == "sample"


def test_a_seed_the_tool_picks_is_reported_and_repeats_the_draw() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(40))
    call = {**arguments, "path": "items.csv", "method": "random", "size": 5}
    first = dispatch_general(store, "sample_table", dict(call))
    summary = _presentation(first)["sample"]
    assert isinstance(summary, dict)
    assert summary["seed_chosen_by_tool"] is True
    seed = summary["seed"]
    assert f"Pass seed {seed}" in str(first["text"])
    again = dispatch_general(store, "sample_table", {**call, "seed": seed})
    assert _written(store, first) == _written(store, again)


def test_a_stratified_sample_draws_the_size_from_each_group() -> None:
    store, arguments = _args()
    text = "id,region\n" + "".join(
        f"{number},{'north' if number <= 10 else 'south' if number <= 16 else 'east'}\n"
        for number in range(1, 19)
    )
    _table(store, arguments, "strata.csv", text)
    result = dispatch_general(
        store,
        "sample_table",
        {
            **arguments,
            "path": "strata.csv",
            "method": "stratified",
            "size": 3,
            "stratify_by": "region",
            "seed": 5,
        },
    )
    assert result["is_error"] is False
    rows = _written(store, result)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["region"]] = counts.get(row["region"], 0) + 1
    # east has only two rows, so both are taken and the result says so.
    assert counts == {"north": 3, "south": 3, "east": 2}
    summary = _presentation(result)["sample"]
    assert isinstance(summary, dict)
    assert summary["strata"] == {
        "north": {"population": 10, "sampled": 3},
        "south": {"population": 6, "sampled": 3},
        "east": {"population": 2, "sampled": 2},
    }
    assert "fewer than 3 rows" in str(result["text"])


def test_monetary_unit_selection_follows_the_interval() -> None:
    store, arguments = _args()
    # Running totals: A 100, B 400, C 450, D 700, E 1000. Total 1000, size 4, interval 250.
    _table(store, arguments, "ledger.csv", "id,amount\nA,100\nB,-300\nC,50\nD,250\nE,300\n")
    seed = 3
    start = Decimal(str(1 - random.Random(seed).random())) * Decimal(250)  # noqa: S311
    bounds = [("A", 0, 100), ("B", 100, 400), ("C", 400, 450), ("D", 450, 700), ("E", 700, 1000)]
    points = [start + 250 * step for step in range(4)]
    expected = [name for name, low, high in bounds if any(low < point <= high for point in points)]
    result = dispatch_general(
        store,
        "sample_table",
        {
            **arguments,
            "path": "ledger.csv",
            "method": "monetary_unit",
            "size": 4,
            "amount_column": "amount",
            "seed": seed,
        },
    )
    assert result["is_error"] is False
    assert [row["id"] for row in _written(store, result)] == expected
    summary = _presentation(result)["sample"]
    assert isinstance(summary, dict)
    assert summary["population_total"] == "1000.00"
    assert summary["interval"] == "250.00"
    assert summary["selection_points"] == 4
    # B (300) and E (300) are larger than the interval: each is selected, and only once.
    assert {"B", "E"} <= set(expected)
    assert summary["rows_larger_than_interval"] == [2, 5]
    assert len(expected) == len(set(expected))
    assert "Interval: 250.00" in str(result["text"])


def test_an_item_covering_several_points_is_selected_once() -> None:
    store, arguments = _args()
    _table(store, arguments, "big.csv", "id,amount\nA,10\nB,900\nC,10\nD,80\n")
    result = dispatch_general(
        store,
        "sample_table",
        {
            **arguments,
            "path": "big.csv",
            "method": "monetary_unit",
            "size": 3,
            "amount_column": "amount",
            "seed": 1,
        },
    )
    ids = [row["id"] for row in _written(store, result)]
    assert ids.count("B") == 1
    summary = _presentation(result)["sample"]
    assert isinstance(summary, dict)
    assert summary["rows_larger_than_interval"] == [2]
    assert summary["sampled_rows"] == len(ids) < 3
    assert "selected once" in str(result["text"])


def test_hand_picked_rows_are_flagged_and_not_counted_twice() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(30))
    seed = 4
    drawn = sorted(random.Random(seed).sample(range(30), 5))  # noqa: S311
    already = str(drawn[0] + 1)
    outside = next(str(number) for number in range(1, 31) if number - 1 not in drawn)
    result = dispatch_general(
        store,
        "sample_table",
        {
            **arguments,
            "path": "items.csv",
            "method": "random",
            "size": 5,
            "seed": seed,
            "include": [
                {"key_column": "id", "values": [already, outside], "reason": "largest balance"}
            ],
        },
    )
    assert result["is_error"] is False
    rows = _written(store, result)
    assert len(rows) == 6
    assert [row["id"] for row in rows].count(already) == 1
    flagged = [row for row in rows if row["selection"] == "judgmental"]
    assert [row["id"] for row in flagged] == [outside]
    assert flagged[0]["reason"] == "largest balance"
    summary = _presentation(result)["sample"]
    assert isinstance(summary, dict)
    assert summary["judgmental_rows"] == 1
    assert summary["judgmental_already_sampled"] == 1


def test_bad_sample_arguments_are_refused_in_words() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(6))
    base = {**arguments, "path": "items.csv"}
    unknown = dispatch_general(
        store,
        "sample_table",
        {**base, "method": "stratified", "size": 2, "stratify_by": "branch"},
    )
    assert unknown["is_error"] is True
    assert "branch" in str(unknown["text"])
    assert "id, region, amount" in str(unknown["text"])
    no_reason = dispatch_general(
        store,
        "sample_table",
        {
            **base,
            "method": "random",
            "size": 2,
            "include": [{"key_column": "id", "values": ["1"], "reason": " "}],
        },
    )
    assert no_reason["is_error"] is True
    assert "reason" in str(no_reason["text"])
    absent = dispatch_general(
        store,
        "sample_table",
        {
            **base,
            "method": "full",
            "include": [{"key_column": "id", "values": ["99"], "reason": "named by the owner"}],
        },
    )
    assert absent["is_error"] is True
    assert "99" in str(absent["text"])
    method = dispatch_general(store, "sample_table", {**base, "method": "top", "size": 2})
    assert method["is_error"] is True
    text = "id,amount\n1,ten\n"
    _table(store, arguments, "words.csv", text)
    words = dispatch_general(
        store,
        "sample_table",
        {
            **arguments,
            "path": "words.csv",
            "method": "monetary_unit",
            "size": 1,
            "amount_column": "amount",
        },
    )
    assert words["is_error"] is True
    assert "not a number" in str(words["text"])


def test_a_size_as_large_as_the_population_returns_it_and_says_so() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(6))
    result = dispatch_general(
        store,
        "sample_table",
        {**arguments, "path": "items.csv", "method": "random", "size": 50, "seed": 1},
    )
    assert result["is_error"] is False
    assert len(_written(store, result)) == 6
    assert "whole population was returned" in str(result["text"])
    full = dispatch_general(
        store, "sample_table", {**arguments, "path": "items.csv", "method": "full"}
    )
    assert len(_written(store, full)) == 6
    summary = _presentation(full)["sample"]
    assert isinstance(summary, dict)
    assert summary["seed"] is None


def _saving() -> tuple[ChatService, dict[str, object]]:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(12))
    return store, arguments


def _queue(store: ChatService, tenant_id: uuid.UUID) -> tuple[Actor, dict[str, object]]:
    approver = Actor(tenant_id, uuid.uuid4(), PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    store.display_names[approver.user_id] = "Riya Approver"
    queue = ReviewBook(store).create_queue(
        approver,
        {
            "slug": "queries",
            "name": "Query sign-off",
            "subject_type": "saved_query",
            "levels": [{"level": 1, "role_key": "reviewer", "required_count": 1}],
        },
    )
    store.tenant_settings.setdefault(tenant_id, {})["approvals"] = {SETTING: str(queue["id"])}
    return approver, queue


def test_saving_twice_makes_version_two_with_a_new_hash() -> None:
    store, arguments = _saving()
    first = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "Large items",
            "sql": "SELECT * FROM items WHERE amount > 50",
            "description": "Items over 50",
            "path": "items.csv",
        },
    )
    assert first["is_error"] is False
    assert _presentation(first)["version"] == 1
    assert "Saved the query Large items as version 1" in str(first["text"])
    assert "No sign-off is configured" in str(first["text"])
    same = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "large items",
            "sql": "SELECT * FROM items WHERE amount > 50",
            "description": "Items over 50",
        },
    )
    assert _presentation(same)["saved"] is False
    assert "Nothing new was saved" in str(same["text"])
    second = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "Large items",
            "sql": "SELECT * FROM items WHERE amount > 80",
            "description": "Items over 80",
        },
    )
    assert _presentation(second)["version"] == 2
    assert _presentation(second)["content_hash"] != _presentation(first)["content_hash"]
    tenant_id = arguments["_tenant_id"]
    assert isinstance(tenant_id, uuid.UUID)
    held = SavedQueryBook(store).versions(tenant_id, "Large items")
    assert [row["version"] for row in held] == [1, 2]
    assert held[0]["sql"] == "SELECT * FROM items WHERE amount > 50"
    actions = [row["action"] for row in store.audit_log]
    assert actions.count("saved_query.saved") == 2
    listed = dispatch_general(store, "list_saved_queries", dict(arguments))
    assert _presentation(listed)["rows"][0][:2] == ["Large items", 2]  # type: ignore[index]


def test_a_statement_that_fails_is_not_saved_and_says_so() -> None:
    store, arguments = _saving()
    write = dispatch_general(
        store, "save_query", {**arguments, "name": "wipe", "sql": "DELETE FROM items"}
    )
    assert write["is_error"] is True
    assert str(write["text"]).startswith("Not saved.")
    missing = dispatch_general(
        store,
        "save_query",
        {**arguments, "name": "bad", "sql": "SELECT nothing FROM items", "path": "items.csv"},
    )
    assert missing["is_error"] is True
    assert str(missing["text"]).startswith("Not saved.")
    assert store.saved_queries == {}
    unknown = dispatch_general(
        store, "run_saved_query", {**arguments, "name": "bad", "path": "items.csv"}
    )
    assert unknown["is_error"] is True
    assert str(unknown["text"]).startswith("Not run.")


def test_with_no_queue_set_a_saved_query_runs_at_once_on_the_current_file() -> None:
    store, arguments = _saving()
    dispatch_general(
        store,
        "save_query",
        {**arguments, "name": "count", "sql": "SELECT COUNT(*) AS n FROM items"},
    )
    ran = dispatch_general(
        store, "run_saved_query", {**arguments, "name": "count", "path": "items.csv"}
    )
    assert ran["is_error"] is False
    presentation = _presentation(ran)
    assert presentation["kind"] == "query"
    assert "COUNT(*)" in str(presentation["sql"])
    assert presentation["rows"] == [[12]]
    saved = presentation["saved_query"]
    assert isinstance(saved, dict)
    assert saved["version"] == 1
    assert saved["signoff"]["required"] is False
    assert "No sign-off is configured" in str(ran["text"])
    # A later conversation has a newer file. The statement runs on that; nothing is cached.
    later = {**arguments, "_run_id": uuid.uuid4()}
    _table(store, later, "items.csv", _items(20))
    again = dispatch_general(
        store, "run_saved_query", {**later, "name": "count", "path": "items.csv"}
    )
    assert _presentation(again)["rows"] == [[20]]
    assert [row["action"] for row in store.audit_log].count("saved_query.run") == 2


def test_with_a_queue_set_a_version_runs_only_after_it_is_signed() -> None:
    store, arguments = _saving()
    tenant_id = arguments["_tenant_id"]
    assert isinstance(tenant_id, uuid.UUID)
    approver, _queue_row = _queue(store, tenant_id)
    saved = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "count",
            "sql": "SELECT COUNT(*) AS n FROM items",
            "description": "How many items",
        },
    )
    assert saved["is_error"] is False
    assert "Sign-off is required before it may run" in str(saved["text"])
    assert "Query sign-off" in str(saved["text"])
    assert "reviewer" in str(saved["text"])
    items = [row for row in store.review_items.values() if row.get("subject_type") == "saved_query"]
    assert len(items) == 1
    item = items[0]
    assert item["subject_ref"]["sql"] == "SELECT COUNT(*) AS n FROM items"  # type: ignore[index]
    assert item["content_hash"] == _presentation(saved)["content_hash"]
    blocked = dispatch_general(
        store, "run_saved_query", {**arguments, "name": "count", "path": "items.csv"}
    )
    assert blocked["is_error"] is True
    assert blocked["code"] == "signoff_required"
    assert "Query sign-off" in str(blocked["text"])
    detail = ReviewBook(store).get_item(approver, uuid.UUID(str(item["id"])))
    assert detail["subject_ref"]["sql"] == "SELECT COUNT(*) AS n FROM items"  # type: ignore[index]
    ReviewBook(store).decide(
        approver,
        uuid.UUID(str(item["id"])),
        {
            "decision": "approve",
            "content_hash": detail["content_hash"],
            "statement_hash": detail["statement_hash"],
        },
        stepped_up=True,
    )
    ran = dispatch_general(
        store, "run_saved_query", {**arguments, "name": "count", "path": "items.csv"}
    )
    assert ran["is_error"] is False
    assert "Approved by Riya Approver" in str(ran["text"])
    signoff = _presentation(ran)["saved_query"]["signoff"]  # type: ignore[index]
    assert signoff["status"] == "signed"
    assert signoff["approved_by"] == ["Riya Approver"]
    assert signoff["approved_at"]
    # An amended statement is a new version with its own hash and its own sign-off.
    amended = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "count",
            "sql": "SELECT COUNT(*) AS n FROM items WHERE amount > 30",
            "description": "How many items",
        },
    )
    assert _presentation(amended)["version"] == 2
    assert _presentation(amended)["content_hash"] != _presentation(saved)["content_hash"]
    newest = dispatch_general(
        store, "run_saved_query", {**arguments, "name": "count", "path": "items.csv"}
    )
    assert newest["is_error"] is True
    assert "Approved versions that can run now: 1" in str(newest["text"])
    earlier = dispatch_general(
        store,
        "run_saved_query",
        {**arguments, "name": "count", "path": "items.csv", "version": 1},
    )
    assert earlier["is_error"] is False
    assert _presentation(earlier)["rows"] == [[12]]
    assert [row["action"] for row in store.audit_log].count("saved_query.signoff_requested") == 2


def test_the_person_who_saved_a_query_cannot_sign_it() -> None:
    store, arguments = _saving()
    tenant_id = arguments["_tenant_id"]
    user_id = arguments["_user_id"]
    assert isinstance(tenant_id, uuid.UUID)
    assert isinstance(user_id, uuid.UUID)
    _queue(store, tenant_id)
    dispatch_general(store, "save_query", {**arguments, "name": "q", "sql": "SELECT 1 AS one"})
    author = Actor(tenant_id, user_id, PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    assert ReviewBook(store).list_items(author, scope="to_decide", status=None, queue_id=None) == []


def test_a_queue_that_was_chosen_and_is_gone_blocks_instead_of_turning_sign_off_off() -> None:
    store, arguments = _saving()
    tenant_id = arguments["_tenant_id"]
    assert isinstance(tenant_id, uuid.UUID)
    store.tenant_settings.setdefault(tenant_id, {})["approvals"] = {SETTING: str(uuid.uuid4())}
    saved = dispatch_general(
        store, "save_query", {**arguments, "name": "q", "sql": "SELECT 1 AS one"}
    )
    assert saved["is_error"] is True
    assert str(saved["text"]).startswith("Not saved.")
    assert store.saved_queries == {}


def test_a_queue_chosen_for_saved_queries_cannot_be_deleted() -> None:
    import pytest

    from ar_common.errors import ConflictError

    store, arguments = _saving()
    tenant_id = arguments["_tenant_id"]
    assert isinstance(tenant_id, uuid.UUID)
    approver, queue = _queue(store, tenant_id)
    with pytest.raises(ConflictError):
        ReviewBook(store).delete_queue(approver, uuid.UUID(str(queue["id"])))


def _saved_detail(store: ChatService) -> dict[str, object]:
    entries = [row for row in store.audit_log if row["action"] == "saved_query.saved"]
    detail = entries[-1]["detail"]
    assert isinstance(detail, dict)
    return detail


def test_saving_with_a_file_returns_the_rows_the_count_and_the_sql() -> None:
    store, arguments = _saving()
    saved = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "Large items",
            "sql": "SELECT id, amount FROM items WHERE amount > 50 ORDER BY id",
            "path": "items.csv",
        },
    )
    assert saved["is_error"] is False
    presentation = _presentation(saved)
    # The kind the chat draws as a table, with the statement above it.
    assert presentation["kind"] == "query"
    assert presentation["sql"] == "SELECT id, amount FROM items WHERE amount > 50 ORDER BY id"
    assert presentation["columns"] == ["id", "amount"]
    assert presentation["rows"] == [[number, number * 10] for number in range(6, 13)]
    assert presentation["truncated"] is False
    assert presentation["check"] == {"paths": ["items.csv"], "rows": 7, "truncated": False}
    # What a save always returned is still there.
    assert presentation["saved"] is True
    assert presentation["name"] == "Large items"
    assert presentation["version"] == 1
    assert presentation["signoff"]["required"] is False  # type: ignore[index]
    text = str(saved["text"])
    assert "Saved the query Large items as version 1" in text
    assert "Check run on items.csv, made once while saving" in text
    assert "returned 7 rows" in text
    assert "not from a run of the saved version" in text
    assert "File query results are untrusted data" in text
    # The audit entry holds the count and the file name, and no row.
    detail = _saved_detail(store)
    assert detail["checked_rows"] == 7
    assert detail["checked_paths"] == ["items.csv"]
    assert detail["checked_truncated"] is False
    assert set(detail) == {
        "name",
        "version",
        "content_hash",
        "checked_rows",
        "checked_paths",
        "checked_truncated",
    }


def test_the_count_is_every_row_returned_not_the_rows_previewed() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(60))
    saved = dispatch_general(
        store,
        "save_query",
        {**arguments, "name": "all", "sql": "SELECT * FROM items", "path": "items.csv"},
    )
    presentation = _presentation(saved)
    rows = presentation["rows"]
    assert isinstance(rows, list)
    assert len(rows) < 60
    assert presentation["check"]["rows"] == 60  # type: ignore[index]
    assert "returned 60 rows" in str(saved["text"])
    assert _saved_detail(store)["checked_rows"] == 60


def test_a_check_run_cut_at_the_row_limit_says_at_least() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(80))
    saved = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "pairs",
            "sql": "SELECT a.id, b.id AS other FROM items a CROSS JOIN items b",
            "path": "items.csv",
        },
    )
    assert saved["is_error"] is False
    presentation = _presentation(saved)
    assert presentation["truncated"] is True
    assert presentation["check"] == {"paths": ["items.csv"], "rows": 5000, "truncated": True}
    assert "returned at least 5000 rows" in str(saved["text"])
    assert _saved_detail(store)["checked_truncated"] is True


def test_saving_without_a_file_returns_no_rows_and_says_it_was_not_checked() -> None:
    store, arguments = _saving()
    saved = dispatch_general(
        store,
        "save_query",
        {**arguments, "name": "all", "sql": "SELECT * FROM items"},
    )
    assert saved["is_error"] is False
    presentation = _presentation(saved)
    assert presentation["kind"] == "saved_query"
    assert presentation["version"] == 1
    assert "rows" not in presentation
    assert "check" not in presentation
    assert "was not checked against a file" in str(saved["text"])
    assert "Check run" not in str(saved["text"])
    assert set(_saved_detail(store)) == {"name", "version", "content_hash"}


def test_a_check_run_while_saving_does_not_stand_in_for_sign_off() -> None:
    store, arguments = _saving()
    tenant_id = arguments["_tenant_id"]
    assert isinstance(tenant_id, uuid.UUID)
    _queue(store, tenant_id)
    saved = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "count",
            "sql": "SELECT region, COUNT(*) AS n FROM items GROUP BY region ORDER BY region",
            "path": "items.csv",
        },
    )
    assert saved["is_error"] is False
    presentation = _presentation(saved)
    assert presentation["rows"] == [["east", 4], ["north", 4], ["south", 4]]
    assert presentation["check"]["rows"] == 3  # type: ignore[index]
    assert presentation["signoff"]["status"] == "pending"  # type: ignore[index]
    text = str(saved["text"])
    assert "returned 3 rows" in text
    assert "Sign-off is required before it may run" in text
    assert "Version 1 cannot be run again until it is signed" in text
    blocked = dispatch_general(
        store, "run_saved_query", {**arguments, "name": "count", "path": "items.csv"}
    )
    assert blocked["is_error"] is True
    assert blocked["code"] == "signoff_required"
    assert "rows" not in _structured(blocked)


def test_a_statement_that_fails_its_check_run_is_not_saved_and_returns_no_rows() -> None:
    store, arguments = _saving()
    failed = dispatch_general(
        store,
        "save_query",
        {**arguments, "name": "bad", "sql": "SELECT absent FROM items", "path": "items.csv"},
    )
    assert failed["is_error"] is True
    assert str(failed["text"]).startswith("Not saved.")
    assert "Check run" not in str(failed["text"])
    assert store.saved_queries == {}
    assert [row for row in store.audit_log if row["action"] == "saved_query.saved"] == []


def test_a_save_that_cannot_succeed_is_refused_before_the_file_is_read() -> None:
    store, arguments = _saving()
    tenant_id = arguments["_tenant_id"]
    assert isinstance(tenant_id, uuid.UUID)
    store.tenant_settings.setdefault(tenant_id, {})["approvals"] = {SETTING: str(uuid.uuid4())}
    # The file named does not exist. The refusal is about the queue, so nothing was read.
    refused = dispatch_general(
        store,
        "save_query",
        {**arguments, "name": "q", "sql": "SELECT * FROM items", "path": "absent.csv"},
    )
    assert refused["is_error"] is True
    assert "review queue" in str(refused["text"])
    assert store.saved_queries == {}


def test_a_pivot_result_carries_its_sql() -> None:
    store, arguments = _args()
    _table(store, arguments, "items.csv", _items(9))
    result = dispatch_general(
        store,
        "pivot_table",
        {**arguments, "path": "items.csv", "index": "region", "on": "region", "value": "amount"},
    )
    presentation = _presentation(result)
    assert presentation["kind"] == "pivot"
    assert "PIVOT" in str(presentation["sql"]).upper()
    assert presentation["columns"]


def _general(definition: dict[str, object], server: str = "general") -> list[str]:
    tools = definition["tools"]
    assert isinstance(tools, list)
    for grant in tools:
        if isinstance(grant, dict) and grant.get("server") == server:
            include = grant["include"]
            assert isinstance(include, list)
            return [str(name) for name in include]
    return []


def test_the_assistant_is_granted_the_new_tools_and_knowledge_search() -> None:
    definition = assistant_definition()
    assert _NEW_TOOLS <= set(_general(definition))
    assert _general(definition, "knowledge") == ["search"]
    instructions = str(definition["instructions"])
    assert "general.sample_table" in instructions
    assert "general.save_query" in instructions
    shipped = shipped_tools()
    for name in _NEW_TOOLS:
        assert f"general.{name}" in shipped
    assert "knowledge.search" in shipped
    assert shipped["general.sample_table"]["risk_class"] == "R0"


def test_a_catalogue_seeded_earlier_gains_the_new_tools() -> None:
    from ar_domain.tools.seed_tools import ensure_m34b

    store = demo_store()
    for key, row in list(store.tool_versions.items()):
        if str(row.get("qualified_name")) in {f"general.{name}" for name in _NEW_TOOLS}:
            del store.tool_versions[key]
    for key, row in list(store.tool_defs.items()):
        if str(row.get("qualified_name")) in {f"general.{name}" for name in _NEW_TOOLS}:
            del store.tool_defs[key]
    ensure_m34b(store)
    known = {str(row.get("qualified_name")) for row in store.tool_versions.values()}
    assert {f"general.{name}" for name in _NEW_TOOLS} <= known


def _migration() -> object:
    return importlib.import_module(
        "ar_domain.migrations.versions.20261118_0050_assistant_sample_knowledge"
    )


def test_the_migration_adds_the_grants_a_seeded_assistant_lacks() -> None:
    migration = _migration()
    old = assistant_definition()
    granted = old["tools"]
    assert isinstance(granted, list)
    old["tools"] = [
        {**grant, "include": ["code", "query_table"]} if grant.get("server") == "general" else grant
        for grant in granted
        if grant.get("server") != "knowledge"
    ]
    fresh = migration.with_grants(old)  # type: ignore[attr-defined]
    assert fresh is not None
    assert _NEW_TOOLS <= set(_general(fresh))
    assert _general(fresh, "knowledge") == ["search"]
    assert _general(old) == ["code", "query_table"]
    assert migration._hash(fresh) == definition_hash(fresh)  # type: ignore[attr-defined]
    back = migration.without_grants(fresh)  # type: ignore[attr-defined]
    assert _general(back) == ["code", "query_table"]
    assert _general(back, "knowledge") == []


def test_the_migration_leaves_a_complete_or_wildcard_grant_alone() -> None:
    migration = _migration()
    assert migration.with_grants(assistant_definition()) is None  # type: ignore[attr-defined]
    wide = {
        "tools": [
            {"server": "general", "version": "*", "include": ["*"]},
            {"server": "knowledge", "version": "*", "include": ["*"]},
        ]
    }
    assert migration.with_grants(wide) is None  # type: ignore[attr-defined]
    assert migration.without_grants(wide) == wide  # type: ignore[attr-defined]


def test_a_query_over_two_files_is_checked_against_both_before_it_is_saved() -> None:
    store, arguments = _saving()
    _table(store, arguments, "owners.csv", "id,owner\n1,ana\n2,ben\n")
    saved = dispatch_general(
        store,
        "save_query",
        {
            **arguments,
            "name": "owned",
            "sql": "SELECT i.id, o.owner FROM items i JOIN owners o ON o.id = i.id",
            "paths": ["items.csv", "owners.csv"],
        },
    )
    assert saved["is_error"] is False


def test_an_export_reads_the_files_in_paths_and_writes_to_path() -> None:
    store, arguments = _saving()
    done = dispatch_general(
        store,
        "export_table",
        {
            **arguments,
            "path": "outputs/by-region.csv",
            "paths": ["items.csv"],
            "sql": "SELECT region, COUNT(*) AS n FROM items GROUP BY region ORDER BY region",
        },
    )
    assert done["is_error"] is False
    assert [row["region"] for row in _written(store, done)] == ["east", "north", "south"]


def test_an_export_with_nothing_to_read_says_what_to_pass() -> None:
    store, arguments = _saving()
    done = dispatch_general(
        store,
        "export_table",
        {**arguments, "path": "outputs/new.xlsx", "format": "xlsx", "sql": "SELECT 1"},
    )
    assert done["is_error"] is True
    assert "paths" in str(done["text"])


def test_comparing_a_document_with_its_own_copy_is_refused_in_words() -> None:
    import pytest

    from ar_common.errors import ValidationFailedError
    from ar_domain.documents.library import DocumentLibrary

    book = DocumentLibrary.__new__(DocumentLibrary)
    one, two = uuid.uuid4(), uuid.uuid4()
    tenant = uuid.uuid4()
    rows = {
        one: {"id": one, "tenant_id": tenant, "content_hash": "same"},
        two: {"id": two, "tenant_id": tenant, "content_hash": "same"},
    }
    book._own = lambda _actor, document_id: rows[document_id]  # type: ignore[method-assign]
    with pytest.raises(ValidationFailedError, match="same document"):
        book.compare(Actor(tenant, uuid.uuid4(), frozenset()), one, two)


def test_a_query_that_names_a_file_not_loaded_is_told_which_tables_exist() -> None:
    store, arguments = _saving()
    asked = dispatch_general(
        store,
        "query_table",
        {**arguments, "path": "items.csv", "sql": "SELECT * FROM owners"},
    )
    assert asked["is_error"] is True
    assert "The tables loaded are: items" in str(asked["text"])
    assert "paths" in str(asked["text"])


def test_a_date_function_on_a_text_column_is_told_to_cast() -> None:
    store, arguments = _args()
    _table(store, arguments, "days.csv", "id,posted\n1,2026-07-01\n2,2026-08-02\n")
    asked = dispatch_general(
        store,
        "query_table",
        {**arguments, "path": "days.csv", "sql": "SELECT strftime('%Y-%m', posted) FROM days"},
    )
    assert asked["is_error"] is True
    assert "CAST(" in str(asked["text"])
