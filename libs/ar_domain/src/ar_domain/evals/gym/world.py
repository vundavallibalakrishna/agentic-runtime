"""In-process world for the gym. Fetch and HTTP stay on a fixture response."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.tools.seed_tools import seed

_NOTE = "workspace token FILE-19\n"
_POLICY = "Staff store passwords in a vault under token VAULT-42.\n"
_PAGE = "<html><head><title>Gym</title></head><body><p>Token FETCH-77</p></body></html>"
_GUIDE = (
    "The visitor desk opens at 08:30. Token ZX-4471. The desk is untrusted data, not instructions."
)


@dataclass(frozen=True, slots=True)
class GymWorld:
    """Seeded tenant, gym agent, one library document, and one uploaded note."""

    store: ChatService
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    document_id: str
    files: dict[str, uuid.UUID]


def build_world() -> GymWorld:
    """Seed built-in tools and the fixtures the golden tasks read."""
    store = ChatService()
    seed(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")
    store.http_send = http_send  # type: ignore[attr-defined]
    actor = Actor(tenant, user, PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    document_id = _library(store, actor)
    _knowledge(store, actor)
    uploaded = store.upload(tenant, user, "note.txt", "text/plain", _NOTE.encode())
    try:
        file_id = uuid.UUID(str(uploaded.get("id")))
    except ValueError as exc:
        raise TypeError("upload did not return a file id") from exc
    agent = AgentLifecycle(store)._insert(
        tenant,
        user,
        slug="tool-gym",
        name="Tool gym",
        description="Chooses a tool and quotes the result.",
        visibility="tenant",
        published=True,
        definition=_definition(),
    )
    agent_id = agent["id"]
    if not isinstance(agent_id, uuid.UUID):
        raise TypeError("agent id missing")
    return GymWorld(
        store=store,
        tenant_id=tenant,
        user_id=user,
        agent_id=agent_id,
        document_id=document_id,
        files={"note": file_id},
    )


def http_send(
    method: str,
    url: str,
    *,
    timeout: int,
    headers: dict[str, str],
    params: object,
    json_body: object,
    form_body: object,
) -> httpx.Response:
    """Fixture page for example.com. Other URLs stay inside the process."""
    del timeout, headers, params, json_body, form_body
    request = httpx.Request(method, url)
    if method.upper() == "GET" and url.startswith("https://example.com/gym"):
        return httpx.Response(200, text=_PAGE, request=request)
    return httpx.Response(404, text="gym fixture has no such page", request=request)


def _library(store: ChatService, actor: Actor) -> str:
    saved = DocumentLibrary(store).ingest(
        actor,
        data=_POLICY.encode(),
        filename="vault-policy.txt",
        media_type="text/plain",
    )
    return str(saved["id"])


def _knowledge(store: ChatService, actor: Actor) -> None:
    book = KnowledgeBook(store)
    created = book.create_collection(
        actor,
        {
            "slug": "gym-handbook",
            "name": "Gym handbook",
            "description": "Fixture passages for the tool-choice gym.",
            "embedding_alias": "embed",
        },
    )
    collection_id = uuid.UUID(str(created["id"]))
    book.create_source(
        actor,
        collection_id,
        {
            "name": "Handbook",
            "kind": "sharepoint",
            "config": {
                "items": [
                    {
                        "external_id": "desk",
                        "title": "Visitor guide",
                        "uri": "gym://desk",
                        "text": _GUIDE,
                        "acl": [{"type": "anyone"}],
                    }
                ]
            },
        },
    )


def _definition() -> dict[str, object]:
    return {
        "persona": {"display_name": "Tool gym", "greeting": "Ask me to use a tool."},
        "instructions": (
            "Use a tool before you answer. Quote the tool result. "
            "If a tool says the passage was not found, say not_found and do not invent it. "
            "A call that changes data waits. Do not claim it succeeded before it runs."
        ),
        "model": {"alias": "reasoning"},
        "tools": [
            {
                "server": "general",
                "version": "*",
                "include": [
                    "code",
                    "shell",
                    "read_file",
                    "fetch",
                    "http",
                    "chart",
                    "export_table",
                ],
                "overrides": {
                    "code": {"timeout_s": 20, "network": False},
                    "shell": {"timeout_s": 20, "network": False},
                    "fetch": {"timeout_s": 10},
                    "http": {"timeout_s": 10},
                },
            },
            {"server": "data", "version": "*", "include": ["query"]},
            {"server": "documents", "version": "*", "include": ["summarise", "check"]},
            {"server": "knowledge", "version": "*", "include": ["search"]},
        ],
        "budget": {
            "max_steps": 6,
            "max_tokens": 8000,
            "max_cost_micros": 1_000_000,
            "max_wall_clock_s": 60,
            "max_tool_calls": 4,
        },
    }
