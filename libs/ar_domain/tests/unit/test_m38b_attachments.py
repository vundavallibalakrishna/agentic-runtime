"""A file attached in chat reaches the agent (M38b-T08, finding F13).

The model was told only the file's name. It had no id and no path to give a tool, so it
made one up. The prompt now names each file with its id and its path in the working
folder, and the file is at that path for every tool, in this turn and in later ones.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.demo_ids import demo_id
from ar_domain.files.attachments import attachment_lines, conversation_attachments
from ar_domain.memory.session import prepare_prompt
from ar_domain.tools.general import dispatch_general
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

TENANT = demo_id("tenant")
USER = demo_id("admin")
CSV = b"region,total\nnorth,120\nsouth,80\n"


def _conversation(store: ChatService) -> uuid.UUID:
    return uuid.UUID(str(store.create_conversation(TENANT, USER, None)["id"]))


def _upload(store: ChatService, name: str, mime: str = "text/csv", data: bytes = CSV) -> uuid.UUID:
    return uuid.UUID(str(store.upload(TENANT, USER, name, mime, data)["id"]))


def _send(
    store: ChatService, conversation_id: uuid.UUID, text: str, files: list[uuid.UUID]
) -> dict[str, object]:
    """Post a message without starting the turn, and finish the run it made."""
    posted = store.post_message(
        TENANT, USER, conversation_id, text, attachment_ids=files, schedule=False
    )
    return store.runs[uuid.UUID(str(posted["run"]["id"]))]


def _prompt(store: ChatService, run: dict[str, object], text: str) -> list[dict[str, str]]:
    conversation = store.conversations[run["conversation_id"]]
    version = store.versions[store.agents[conversation["agent_id"]]["published_version_id"]]
    prepare_prompt(store, run, conversation, version["definition"], text)
    return run["prompt_messages"]


def _finish(store: ChatService, run: dict[str, object]) -> None:
    run["status"] = "completed"
    store.conversations[run["conversation_id"]]["active_run_id"] = None


def test_the_prompt_names_an_attached_file_with_its_id_and_path() -> None:
    store = demo_store()
    conversation_id = _conversation(store)
    file_id = _upload(store, "orders.csv")
    run = _send(store, conversation_id, "Total this by region", [file_id])
    asked = _prompt(store, run, "Total this by region")[-1]["content"]
    line = f"[file: orders.csv (text/csv, {len(CSV)} B) id={file_id} path=inputs/orders.csv]"
    assert line in asked
    # The person's own words are not wrapped as untrusted data. The file lines are.
    assert asked.startswith("Total this by region\n\n")
    assert asked.index("<untrusted_content") < asked.index(line)


def test_a_message_without_files_is_sent_as_it_was_written() -> None:
    store = demo_store()
    run = _send(store, _conversation(store), "Hello", [])
    assert _prompt(store, run, "Hello")[-1]["content"] == "Hello"


def test_the_file_is_at_the_path_the_prompt_names() -> None:
    store = demo_store()
    conversation_id = _conversation(store)
    file_id = _upload(store, "orders.csv")
    run = _send(store, conversation_id, "Total this", [file_id])
    who = {
        "_tenant_id": TENANT,
        "_user_id": USER,
        "_run_id": run["id"],
        "_conversation_id": conversation_id,
    }
    listed = dispatch_general(store, "list_files", dict(who))
    assert "inputs/orders.csv" in str(listed["text"]).splitlines()
    for path in ("inputs/orders.csv", "./inputs/orders.csv", "/workspace/inputs/orders.csv"):
        read = dispatch_general(store, "read_file", {**who, "path": path})
        assert read["is_error"] is False, path
        assert "north,120" in str(read["text"])


def test_a_later_turn_still_has_the_file() -> None:
    """The file belongs to the conversation, not to the turn that brought it."""
    store = demo_store()
    conversation_id = _conversation(store)
    file_id = _upload(store, "orders.csv")
    first = _send(store, conversation_id, "Total this by region", [file_id])
    _finish(store, first)
    second = _send(store, conversation_id, "Now only the north", [])
    messages = _prompt(store, second, "Now only the north")
    earlier = next(item for item in messages if item["content"].startswith("Total this"))
    assert f"id={file_id} path=inputs/orders.csv" in earlier["content"]
    assert messages[-1]["content"] == "Now only the north"
    read = dispatch_general(
        store,
        "read_file",
        {
            "_tenant_id": TENANT,
            "_user_id": USER,
            "_run_id": second["id"],
            "_conversation_id": conversation_id,
            "path": "inputs/orders.csv",
        },
    )
    assert "south,80" in str(read["text"])


def test_two_files_with_one_name_get_two_paths() -> None:
    store = demo_store()
    conversation_id = _conversation(store)
    january = _upload(store, "report.csv", data=b"month\njan\n")
    february = _upload(store, "report.csv", data=b"month\nfeb\n")
    first = _send(store, conversation_id, "January", [january])
    _finish(store, first)
    second = _send(store, conversation_id, "February, and January again", [february, january])
    found = conversation_attachments(store, conversation_id)
    assert [item.file_id for item in found] == [january, february], "a file is listed once"
    assert found[0].path == "inputs/report.csv"
    assert found[1].path == f"inputs/report-{february.hex[:8]}.csv"
    who = {
        "_tenant_id": TENANT,
        "_user_id": USER,
        "_run_id": second["id"],
        "_conversation_id": conversation_id,
    }
    assert "jan" in str(dispatch_general(store, "read_file", {**who, "path": found[0].path}))
    assert "feb" in str(dispatch_general(store, "read_file", {**who, "path": found[1].path}))


def test_a_deleted_file_and_another_tenants_file_are_not_listed() -> None:
    store = demo_store()
    conversation_id = _conversation(store)
    kept = _upload(store, "kept.csv")
    gone = _upload(store, "gone.csv")
    theirs = _upload(store, "theirs.csv")
    _send(store, conversation_id, "Three files", [kept, gone, theirs])
    store.files[gone]["deleted_at"] = "2026-11-06T00:00:00+00:00"
    store.files[theirs]["tenant_id"] = uuid.uuid4()
    found = conversation_attachments(store, conversation_id)
    assert [item.name for item in found] == ["kept.csv"]
    assert "gone.csv" not in attachment_lines(found)
    assert conversation_attachments(store, uuid.uuid4()) == []
    assert conversation_attachments(store, None) == []


def test_a_file_name_cannot_leave_the_inputs_folder() -> None:
    store = demo_store()
    conversation_id = _conversation(store)
    file_id = _upload(store, "../../etc/passwd.csv")
    _send(store, conversation_id, "Read it", [file_id])
    (found,) = conversation_attachments(store, conversation_id)
    assert found.path.startswith("inputs/")
    assert "/" not in found.path.removeprefix("inputs/")
    assert ".." not in found.path.split("/")
