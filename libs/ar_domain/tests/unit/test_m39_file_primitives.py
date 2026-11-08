"""Workspace file primitives: edit, grep, glob, move, delete, read by line. Task: M39-T03."""

from __future__ import annotations

import uuid
from typing import Any

from ar_domain.demo_ids import demo_id
from ar_domain.tools.general import dispatch_general
from ar_testing.demo import demo_store


def _ctx() -> dict[str, Any]:
    return {
        "_tenant_id": demo_id("tenant"),
        "_user_id": demo_id("admin"),
        "_run_id": uuid.uuid4(),
    }


def _store_with(ctx: dict[str, Any], path: str, content: str) -> Any:
    store = demo_store()
    result = dispatch_general(store, "write_file", {**ctx, "path": path, "content": content})
    assert result["is_error"] is False
    return store


def test_read_file_takes_a_line_range() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "a.txt", "one\ntwo\nthree\nfour\n")
    read = dispatch_general(store, "read_file", {**ctx, "path": "a.txt", "offset": 1, "limit": 2})
    assert read["text"] == "two\nthree"


def test_edit_file_replaces_an_exact_string() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "code.py", "x = 1\ny = 2\n")
    edited = dispatch_general(
        store, "edit_file", {**ctx, "path": "code.py", "oldString": "y = 2", "newString": "y = 9"}
    )
    assert edited["is_error"] is False
    after = dispatch_general(store, "read_file", {**ctx, "path": "code.py"})
    assert after["text"] == "x = 1\ny = 9"


def test_edit_file_refuses_an_ambiguous_match_without_replace_all() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "c.py", "n = 1\nn = 2\n")
    ambiguous = dispatch_general(
        store, "edit_file", {**ctx, "path": "c.py", "oldString": "n = ", "newString": "m = "}
    )
    assert ambiguous["is_error"] is True
    assert ambiguous["code"] == "ambiguous_edit"
    done = dispatch_general(
        store,
        "edit_file",
        {**ctx, "path": "c.py", "oldString": "n = ", "newString": "m = ", "replaceAll": True},
    )
    assert "2 replacements" in str(done["text"])


def test_edit_file_reports_a_missing_string() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "c.py", "a = 1\n")
    missing = dispatch_general(
        store, "edit_file", {**ctx, "path": "c.py", "oldString": "zzz", "newString": "q"}
    )
    assert missing["is_error"] is True
    assert missing["code"] == "not_found"


def test_grep_returns_path_line_and_text() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "src/a.py", "import os\nimport sys\nvalue = 1\n")
    dispatch_general(store, "write_file", {**ctx, "path": "src/b.txt", "content": "nothing here\n"})
    found = dispatch_general(store, "grep", {**ctx, "pattern": r"^import ", "glob": "**/*.py"})
    assert "src/a.py:1: import os" in found["text"]
    assert "src/a.py:2: import sys" in found["text"]
    assert "b.txt" not in found["text"]


def test_glob_matches_by_name() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "one.py", "x\n")
    dispatch_general(store, "write_file", {**ctx, "path": "sub/two.py", "content": "y\n"})
    dispatch_general(store, "write_file", {**ctx, "path": "note.md", "content": "z\n"})
    matched = dispatch_general(store, "glob", {**ctx, "pattern": "**/*.py"})
    assert "one.py" in matched["text"]
    assert "sub/two.py" in matched["text"]
    assert "note.md" not in matched["text"]


def test_move_relocates_a_file_and_the_source_is_gone() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "draft.txt", "hello\n")
    moved = dispatch_general(
        store, "move", {**ctx, "source": "draft.txt", "destination": "final/report.txt"}
    )
    assert moved["is_error"] is False
    listed = dispatch_general(store, "glob", {**ctx, "pattern": "**/*.txt"})
    assert "final/report.txt" in listed["text"]
    assert "draft.txt" not in listed["text"]
    gone = dispatch_general(store, "read_file", {**ctx, "path": "draft.txt"})
    assert gone["is_error"] is True


def test_delete_removes_a_file_for_later_calls() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "temp.txt", "scratch\n")
    removed = dispatch_general(store, "delete", {**ctx, "path": "temp.txt"})
    assert removed["is_error"] is False
    listed = dispatch_general(store, "glob", {**ctx, "pattern": "**/*.txt"})
    assert "No files match" in listed["text"]


def test_primitives_stay_inside_the_workspace() -> None:
    ctx = _ctx()
    store = _store_with(ctx, "a.txt", "x\n")
    for name, args in (
        ("edit_file", {"path": "../escape", "oldString": "a", "newString": "b"}),
        ("move", {"source": "../x", "destination": "y"}),
        ("delete", {"path": "/etc/passwd"}),
    ):
        result = dispatch_general(store, name, {**ctx, **args})
        assert result["is_error"] is True
