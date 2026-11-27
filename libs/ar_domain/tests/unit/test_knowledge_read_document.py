"""knowledge.get_document returns a document's text a page at a time (spec 08). Proof: unit."""

import asyncio
import uuid

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.knowledge.book import KnowledgeBook, _joined
from ar_domain.knowledge.members import add_member
from ar_domain.tools.handlers import _knowledge
from ar_testing.demo import demo_store

LIST = "\n".join(f"- Item number {index}: a named entry on the page." for index in range(1, 61))


def _library(store: object, tenant: uuid.UUID, title: str, text: str) -> uuid.UUID:
    document_id = uuid.uuid4()
    store.library_documents[document_id] = {  # type: ignore[attr-defined]
        "id": document_id,
        "tenant_id": tenant,
        "title": title,
        "content_hash": title,
        "passages": [
            {"text": part, "anchor": f"p1-s{index}", "page": 1, "heading": title}
            for index, part in enumerate(text.split("\n\n"))
        ],
    }
    return document_id


def _setup() -> tuple[object, Actor, str]:
    store = demo_store()
    actor = Actor(
        demo_id("tenant"),
        demo_id("admin"),
        frozenset({"knowledge:manage", "knowledge:read", "chat:use"}),
    )
    created = KnowledgeBook(store).create_collection(actor, {"name": "Site", "slug": "site"})
    collection_id = uuid.UUID(created["id"])
    halves = LIST.splitlines()
    text = "\n".join(halves[:30]) + "\n\n" + "\n".join(halves[30:])
    library_id = _library(store, actor.tenant_id, "Partners page", text)
    asyncio.run(
        add_member(
            store, actor, collection_id, {"kind": "library", "library_document_id": str(library_id)}
        )
    )
    return store, actor, "Partners page"


def _call(store: object, actor: Actor, **arguments: object) -> dict[str, object]:
    return _knowledge(
        store,
        "get_document",
        {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id, **arguments},
    )


def test_the_text_has_every_item_and_says_where_it_ends() -> None:
    store, actor, title = _setup()
    whole = _call(store, actor, document_id=title)
    assert whole["is_error"] is False
    text = str(whole["text"])
    assert "Item number 1:" in text
    assert "Item number 60:" in text
    assert text.endswith("[End of the document.]")


def test_a_part_at_a_time_reaches_the_end() -> None:
    store, actor, title = _setup()
    first = _call(store, actor, document_id=title, limit=400)
    structured = first["structured"]
    assert isinstance(structured, dict)
    following = structured["next_offset"]
    assert isinstance(following, int)
    assert f"offset {following}" in str(first["text"])
    seen = str(structured["text"])
    while isinstance(following, int):
        part = _call(store, actor, document_id=title, offset=following)
        body = part["structured"]
        assert isinstance(body, dict)
        seen += str(body["text"])
        following = body["next_offset"]  # type: ignore[assignment]
    assert "Item number 60:" in seen


def test_an_unknown_name_is_not_found() -> None:
    store, actor, _title = _setup()
    missing = _call(store, actor, document_id="A page nobody wrote")
    assert missing["is_error"] is True


def test_another_tenant_cannot_read_it() -> None:
    store, _actor, title = _setup()
    stranger = Actor(uuid.uuid4(), uuid.uuid4(), frozenset({"knowledge:read"}))
    refused = _call(store, stranger, document_id=title)
    assert refused["is_error"] is True


def test_passages_are_joined_without_the_repeated_overlap() -> None:
    assert _joined(["one two three four", "three four five six"]) == "one two three four five six"
    assert _joined(["alpha", "beta"]) == "alpha\nbeta"
    assert _joined(["", "only"]) == "only"


def test_an_agent_bound_to_its_collection_can_read_a_document_in_it() -> None:
    store, actor, title = _setup()
    version_id = uuid.uuid4()
    store.versions[version_id] = {  # type: ignore[attr-defined]
        "id": version_id,
        "definition": {"knowledge": {"collections": ["site"]}},
    }
    bound = _call(store, actor, document_id=title, _agent_version_id=version_id)
    assert bound["is_error"] is False
    assert "Item number 60:" in str(bound["text"])
    store.versions[version_id]["definition"] = {"knowledge": {"collections": ["other"]}}  # type: ignore[attr-defined]
    elsewhere = _call(store, actor, document_id=title, _agent_version_id=version_id)
    assert elsewhere["is_error"] is True
