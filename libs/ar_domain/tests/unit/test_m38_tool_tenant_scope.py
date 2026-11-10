"""Built-in read tools stay inside the caller's tenant. Task: M38-T01."""

import uuid
from typing import TYPE_CHECKING

from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def _who(tenant: uuid.UUID, user: uuid.UUID) -> dict[str, object]:
    return {"_tenant_id": tenant, "_user_id": user}


def _say(
    store: ChatService,
    tenant: uuid.UUID,
    user: uuid.UUID,
    text: str,
    agent: uuid.UUID | None = None,
) -> uuid.UUID:
    conversation_id, message_id = uuid.uuid4(), uuid.uuid4()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": tenant,
        "user_id": user,
        "agent_id": agent,
        "deleted_at": None,
    }
    store.messages[message_id] = {
        "id": message_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "role": "user",
        "text": text,
        "author_user_id": user,
    }
    return conversation_id


def _file(
    store: ChatService,
    tenant: uuid.UUID,
    owner: uuid.UUID | None,
    name: str,
    data: bytes,
    conversation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "conversation_id": conversation_id,
        "name": name,
        "status": "ready",
        "deleted_at": None,
    }
    store.blobs[file_id] = data
    return file_id


def _tool(store: ChatService, tenant: uuid.UUID, slug: str, description: str) -> None:
    server_id, version_id, tool_id, tool_version_id = (uuid.uuid4() for _ in range(4))
    store.tool_servers[server_id] = {
        "id": server_id,
        "tenant_id": tenant,
        "slug": slug,
        "status": "approved",
        "disabled_at": None,
        "current_version_id": version_id,
    }
    store.tool_server_versions[version_id] = {
        "id": version_id,
        "tenant_id": tenant,
        "tool_server_id": server_id,
    }
    store.tool_defs[tool_id] = {
        "id": tool_id,
        "tenant_id": tenant,
        "tool_server_id": server_id,
        "disabled_at": None,
    }
    store.tool_versions[tool_version_id] = {
        "id": tool_version_id,
        "tenant_id": tenant,
        "tool_id": tool_id,
        "tool_server_version_id": version_id,
        "name": "lookup",
        "qualified_name": f"{slug}.lookup",
        "description": description,
    }


def _history(store: ChatService, who: dict[str, object], query: str) -> str:
    return str(
        dispatch(store, "builtin://conversations", "search_history", {"query": query, **who}, "")[
            "text"
        ]
    )


def test_history_search_reads_only_the_callers_own_conversations() -> None:
    store = demo_store()
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    alice, bob, carol = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    _say(store, tenant_a, alice, "zebra plan for alice")
    _say(store, tenant_a, bob, "zebra salary for bob")
    _say(store, tenant_b, carol, "zebra merger for carol")

    assert _history(store, _who(tenant_a, alice), "zebra") == "zebra plan for alice"
    assert _history(store, _who(tenant_b, carol), "zebra") == "zebra merger for carol"
    assert _history(store, _who(tenant_b, alice), "zebra") == "No earlier messages."
    assert _history(store, {}, "zebra") == "No earlier messages.", "no caller, no rows"


def test_history_search_stays_with_the_calling_agent() -> None:
    store = demo_store()
    tenant, alice = uuid.uuid4(), uuid.uuid4()
    helpdesk, finance = uuid.uuid4(), uuid.uuid4()
    _say(store, tenant, alice, "zebra printer is jammed", agent=helpdesk)
    _say(store, tenant, alice, "zebra invoice is late", agent=finance)

    asked_by_helpdesk = {**_who(tenant, alice), "_agent_id": helpdesk}
    assert _history(store, asked_by_helpdesk, "zebra") == "zebra printer is jammed"


def test_files_list_and_read_stay_with_the_caller() -> None:
    store = demo_store()
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    alice, bob, carol = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    thread = _say(store, tenant_a, alice, "hello")
    mine = _file(store, tenant_a, alice, "alice-notes.txt", b"alice secret")
    made_here = _file(store, tenant_a, None, "chart.png", b"chart", conversation_id=thread)
    colleague = _file(store, tenant_a, bob, "bob-payroll.txt", b"bob secret")
    other = _file(store, tenant_b, carol, "carol-merger.txt", b"carol secret")
    orphan = uuid.uuid4()
    store.blobs[orphan] = b"export of everything"

    listed = dispatch(store, "builtin://files", "list", _who(tenant_a, alice), "")
    assert listed["structured"] == {"files": ["alice-notes.txt", "chart.png"]}

    def read(file_id: uuid.UUID, who: dict[str, object]) -> dict[str, object]:
        return dispatch(store, "builtin://files", "read", {"file_id": str(file_id), **who}, "")

    assert read(mine, _who(tenant_a, alice))["text"] == "alice secret"
    assert read(made_here, _who(tenant_a, alice))["text"] == "chart"
    for hidden in (colleague, other, orphan):
        refused = read(hidden, _who(tenant_a, alice))
        assert refused["is_error"] is True
        assert refused["code"] == "not_found"
        assert "secret" not in str(refused["text"])
    assert read(mine, {})["code"] == "not_found", "no caller, no file"
    store.files[mine]["deleted_at"] = "2026-11-05"
    assert read(mine, _who(tenant_a, alice))["code"] == "not_found"


def test_tool_search_ranks_platform_and_own_tenant_tools_only() -> None:
    store = demo_store()
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    user = uuid.uuid4()
    _tool(store, tenant_a, "alpha", "Look up a quasar invoice for tenant a.")
    _tool(store, tenant_b, "bravo", "Look up a quasar payroll row for tenant b.")

    def names(who: dict[str, object]) -> list[str]:
        found = dispatch(store, "builtin://session", "search", {"query": "quasar", **who}, "")
        tools = found["structured"]["tools"]  # type: ignore[index]
        return [str(row["qualified_name"]) for row in tools]

    seen_by_a = names(_who(tenant_a, user))
    assert "alpha.lookup" in seen_by_a
    assert "bravo.lookup" not in seen_by_a
    assert "bravo.lookup" in names(_who(tenant_b, user))
    assert "alpha.lookup" not in names({}) and "bravo.lookup" not in names({})
    platform = dispatch(store, "builtin://session", "search", {"query": "files"}, "")
    assert "files.list" in str(platform["text"]), "platform tools stay searchable"


def test_tool_search_skips_disabled_and_superseded_versions() -> None:
    store = demo_store()
    tenant = uuid.uuid4()
    who = _who(tenant, uuid.uuid4())
    _tool(store, tenant, "alpha", "Look up a quasar invoice.")
    server = next(row for row in store.tool_servers.values() if row.get("slug") == "alpha")

    def found() -> str:
        return str(
            dispatch(store, "builtin://session", "search", {"query": "quasar", **who}, "")["text"]
        )

    assert "alpha.lookup" in found()
    server["status"] = "pending_review"
    assert "alpha.lookup" not in found()
    server["status"] = "approved"
    server["current_version_id"] = uuid.uuid4()
    assert "alpha.lookup" not in found()
