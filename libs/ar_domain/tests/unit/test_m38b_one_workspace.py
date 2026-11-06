"""File tools and code share one folder and one way to name a file (M38b-T08, finding F14).

``write_file`` reported ``/workspace/orders.csv`` and Python could not open it: on a host
without user namespaces the code runs in the folder, but ``/workspace`` does not exist
there. Tools now show a path relative to the working folder, which is where code and
shell commands start, so the path one tool returns works in the others on any host.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from ar_common.isolate import isolation_mode
from ar_common.sandboxkit import PathEscapeError, confine, relative_path, working_path
from ar_domain.demo_ids import demo_id
from ar_domain.tools.general import dispatch_general
from ar_testing.demo import demo_store

TENANT = demo_id("tenant")
USER = demo_id("admin")


def _who(conversation_id: uuid.UUID | None = None) -> dict[str, object]:
    return {
        "_tenant_id": TENANT,
        "_user_id": USER,
        "_run_id": uuid.uuid4(),
        "_conversation_id": conversation_id,
    }


def _run(store: object, conversation_id: uuid.UUID, created_at: str) -> dict[str, object]:
    run_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": TENANT,
        "conversation_id": conversation_id,
        "status": "completed",
        "created_at": created_at,
    }
    return {
        "_tenant_id": TENANT,
        "_user_id": USER,
        "_run_id": run_id,
        "_conversation_id": conversation_id,
    }


def test_a_relative_path_is_inside_the_working_folder() -> None:
    assert working_path("orders.csv") == "/workspace/orders.csv"
    assert working_path("./inputs/orders.csv") == "/workspace/inputs/orders.csv"
    assert working_path("") == "/workspace"
    assert working_path(".") == "/workspace"
    assert working_path("/workspace/a.txt") == "/workspace/a.txt"
    assert working_path("/tmp/a.txt") == "/tmp/a.txt"  # noqa: S108 - the sandbox's own /tmp


def test_a_path_cannot_leave_the_working_folder(tmp_path: Path) -> None:
    for raw in ("../secret", "inputs/../../secret", "/etc/passwd", "/workspace/../etc/passwd"):
        with pytest.raises(PathEscapeError):
            confine(tmp_path, raw)
    inside = confine(tmp_path, "inputs/orders.csv")
    assert inside == (tmp_path / "workspace").resolve() / "inputs" / "orders.csv"
    assert relative_path(tmp_path, inside) == "inputs/orders.csv"
    assert relative_path(tmp_path, confine(tmp_path, "")) == "."


def test_python_opens_a_file_by_the_path_write_file_returned() -> None:
    store = demo_store()
    who = _who()
    wrote = dispatch_general(
        store, "write_file", {**who, "path": "orders.csv", "content": "region,total\nnorth,120\n"}
    )
    path = wrote["structured"]["presentation"]["path"]
    assert path == "orders.csv"
    assert str(wrote["text"]) == "Wrote orders.csv"
    ran = dispatch_general(
        store, "code", {**who, "source": f"print(open({path!r}).read().splitlines()[1])"}
    )
    assert ran["is_error"] is False, ran["text"]
    assert "north,120" in str(ran["text"])


def test_a_file_tool_reads_what_python_wrote_and_the_shell_sees_both() -> None:
    store = demo_store()
    who = _who()
    dispatch_general(store, "write_file", {**who, "path": "notes/a.txt", "content": "from a tool"})
    ran = dispatch_general(
        store,
        "code",
        {
            **who,
            "source": (
                "import os\nos.makedirs('out', exist_ok=True)\n"
                "open('out/b.txt', 'w').write('from python')\n"
            ),
        },
    )
    assert ran["is_error"] is False, ran["text"]
    read = dispatch_general(store, "read_file", {**who, "path": "out/b.txt"})
    assert str(read["text"]) == "from python"
    listed = str(dispatch_general(store, "list_files", dict(who))["text"]).splitlines()
    assert {"notes/a.txt", "out/b.txt"} <= set(listed)
    shell = dispatch_general(store, "shell", {**who, "command": "cat notes/a.txt out/b.txt"})
    assert shell["is_error"] is False, shell["text"]
    assert "from a tool" in str(shell["text"])
    assert "from python" in str(shell["text"])


def test_the_next_turn_finds_what_the_last_turn_wrote() -> None:
    """A conversation has one working folder: a finished turn's files are there in the next."""
    store = demo_store()
    conversation_id = uuid.uuid4()
    first = _run(store, conversation_id, "2026-11-06T10:00:00+00:00")
    second = _run(store, conversation_id, "2026-11-06T10:05:00+00:00")
    third = _run(store, conversation_id, "2026-11-06T10:10:00+00:00")
    dispatch_general(store, "write_file", {**first, "path": "draft.md", "content": "first turn"})
    read = dispatch_general(store, "read_file", {**second, "path": "draft.md"})
    assert str(read["text"]) == "first turn"
    dispatch_general(store, "write_file", {**second, "path": "draft.md", "content": "second turn"})
    read = dispatch_general(store, "read_file", {**third, "path": "draft.md"})
    assert str(read["text"]) == "second turn", "the latest turn's copy wins"


def test_another_conversation_does_not_see_the_files() -> None:
    store = demo_store()
    mine = _run(store, uuid.uuid4(), "2026-11-06T10:00:00+00:00")
    other = _run(store, uuid.uuid4(), "2026-11-06T10:05:00+00:00")
    dispatch_general(store, "write_file", {**mine, "path": "private.txt", "content": "mine"})
    read = dispatch_general(store, "read_file", {**other, "path": "private.txt"})
    assert read["is_error"] is True
    assert read["code"] == "not_found"


def test_a_command_that_names_a_missing_workspace_folder_is_told_what_to_use() -> None:
    """Where ``/workspace`` is not real, a failed command says so and names the way out."""
    store = demo_store()
    who = _who()
    ran = dispatch_general(
        store, "code", {**who, "source": "open('/workspace/result.csv', 'w').write('a,b')"}
    )
    if isolation_mode() == "namespace":
        assert ran["is_error"] is False, "a private root has a real /workspace"
        return
    assert ran["is_error"] is True
    assert "has no /workspace folder" in str(ran["text"])
    assert "relative to it" in str(ran["text"])
    again = dispatch_general(
        store, "code", {**who, "source": "open('result.csv', 'w').write('a,b')"}
    )
    assert again["is_error"] is False, again["text"]
    assert str(dispatch_general(store, "read_file", {**who, "path": "result.csv"})["text"]) == "a,b"


def test_a_failed_command_does_not_show_the_hosts_folder() -> None:
    store = demo_store()
    ran = dispatch_general(store, "code", {**_who(), "source": "raise SystemExit(open('nope'))"})
    assert ran["is_error"] is True
    assert "ar-run-workspaces" not in str(ran["text"])
    assert "ar-run-workspaces" not in str(ran["structured"])


def test_a_wrong_path_is_answered_with_what_the_folder_holds() -> None:
    """One wrong guess is recoverable: the answer names the files that are there."""
    store = demo_store()
    who = _who()
    empty = dispatch_general(store, "read_file", {**who, "path": "totals.csv"})
    assert empty["code"] == "not_found"
    assert str(empty["text"]) == "Nothing is at totals.csv. The working folder is empty."
    dispatch_general(store, "write_file", {**who, "path": "region_totals.csv", "content": "a"})
    dispatch_general(store, "write_file", {**who, "path": "notes/b.txt", "content": "b"})
    missed = dispatch_general(store, "read_file", {**who, "path": "workspace/region_totals.csv"})
    assert missed["code"] == "not_found"
    assert str(missed["text"]) == (
        "Nothing is at workspace/region_totals.csv. "
        "The working folder holds: notes/b.txt, region_totals.csv."
    )
    folder = dispatch_general(store, "list_files", {**who, "path": "reports"})
    assert "The working folder holds: notes/b.txt, region_totals.csv." in str(folder["text"])
