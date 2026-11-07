"""A scripted model that a store reaches like any provider.

The server is real and listens on loopback. A test registers it through the calls a
person uses (a provider, a model, the aliases), so the code under test takes the path
it takes with a customer's model. Spec: docs/08-quality/testing-strategy.md §4.
"""

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from ar_fake_llm.app import create_application
from ar_fake_llm.background import BackgroundServer
from ar_fake_llm.scripts import Script

if TYPE_CHECKING:
    from collections.abc import Iterator

MODEL = "stand-in-chat"
EMBEDDING_MODEL = "stand-in-embed"
RERANK_MODEL = "stand-in-rerank"
MEMORY_MODEL = "stand-in-memory"
MEMORY_SET = "memory"

_EXTRACTION = "You decide what an assistant should remember"
# Only the person's own words are matched: the block ends at the next tag.
_SAID = r"(?is)<person_said>[^<]*?\b"
_REST = r"\s+([^.\n<]+)"


def _memory(phrase: str, content: str, category: str) -> dict[str, object]:
    answer = (
        '[{"op": "add", "content": "' + content + '", "category": "' + category + '", '
        '"scope": "user", "confidence": 0.95, "explicit": true}]'
    )
    return {
        "match": {"system_contains": _EXTRACTION, "regex": _SAID + phrase + _REST},
        "respond": {"text": answer},
    }


# What the stand-in answers when it is asked what to remember from a turn. A real model
# reads the turn; the stand-in recognises two ways of saying it, which is enough for a test
# to drive the product's extraction end to end. Anything else changes nothing.
MEMORY_SCRIPTS: list[dict[str, object]] = [
    _memory("remember that i prefer", "Prefers {{group:1}}", "preference"),
    _memory("remember that", "{{group:1}}", "fact"),
    _memory("i prefer", "Prefers {{group:1}}", "preference"),
    {"match": {"system_contains": _EXTRACTION}, "respond": {"text": "[]"}},
]


class StandIn:
    """One scripted model server for a test session."""

    def __init__(self) -> None:
        self.app = create_application()
        self._server = BackgroundServer(self.app)
        self.port = self._server.start()

    def base_url(self, script_set: str = "default") -> str:
        """The OpenAI-compatible base URL that answers from ``script_set``."""
        return f"http://127.0.0.1:{self.port}/s/{script_set}/v1"

    def script(self, script_set: str, scripts: list[dict[str, object]]) -> None:
        """Replace a script set. The first script that matches a request answers it."""
        self.app.state.scripts.register(
            script_set, [Script.model_validate(item) for item in scripts]
        )

    def connect(
        self,
        store: Any,
        tenant_id: uuid.UUID,
        *,
        script_set: str = "default",
        aliases: tuple[str, ...] = ("reasoning", "fast"),
        capabilities: list[str] | None = None,
    ) -> uuid.UUID:
        """Register the stand-in as the tenant's model and return the model id.

        The store must allow loopback provider URLs, as a development store does.
        ``capabilities`` marks the model, e.g. ``["vision"]`` to let it read images.
        """
        provider = store.create_provider(
            tenant_id,
            f"stand-in-{script_set}",
            "openai_compatible",
            self.base_url(script_set),
            platform=False,
        )
        model = store.create_model(
            tenant_id,
            uuid.UUID(str(provider["id"])),
            f"stand-in-{script_set}",
            MODEL,
            "chat",
            platform=False,
            capabilities=capabilities,
        )
        model_id = uuid.UUID(str(model["id"]))
        for alias in aliases:
            own = next(
                (
                    row
                    for row in store.aliases.values()
                    if row.get("tenant_id") == tenant_id and row.get("alias") == alias
                ),
                None,
            )
            if own is None:
                store.create_alias(tenant_id, alias, "chat", model_id, platform=False)
            else:
                store.update_alias(tenant_id, uuid.UUID(str(own["id"])), model_id, platform=False)
        return model_id

    def connect_embeddings(self, store: Any, tenant_id: uuid.UUID | None = None) -> uuid.UUID:
        """Register the stand-in's embedding and rerank models and return the embedding id.

        The ``embed`` and ``rerank`` aliases point at them, for ``tenant_id`` or, with
        none, for every tenant of the store. The vectors are stable for a text and carry
        no meaning, so a test that needs a passage found relies on the words they share.
        The store must allow loopback provider URLs. Calling it twice changes nothing.
        """
        platform = tenant_id is None
        provider = _owned(store.providers, tenant_id, "name", "stand-in-embeddings")
        if provider is None:
            provider = store.create_provider(
                tenant_id,
                "stand-in-embeddings",
                "openai_compatible",
                self.base_url("embeddings"),
                platform=platform,
            )
        provider_id = uuid.UUID(str(provider["id"]))
        found: dict[str, uuid.UUID] = {}
        for alias, kind, name in (
            ("embed", "embedding", EMBEDDING_MODEL),
            ("rerank", "rerank", RERANK_MODEL),
        ):
            model = _owned(store.models, tenant_id, "upstream_model", name)
            if model is None:
                model = store.create_model(
                    tenant_id, provider_id, name, name, kind, platform=platform
                )
            found[alias] = uuid.UUID(str(model["id"]))
            if _owned(store.aliases, tenant_id, "alias", alias) is None:
                store.create_alias(tenant_id, alias, kind, found[alias], platform=platform)
        return found["embed"]

    def connect_extraction(
        self, store: Any, tenant_id: uuid.UUID | None = None, *, script_set: str = MEMORY_SET
    ) -> uuid.UUID:
        """Point the ``fast`` alias at the stand-in, which answers what to remember.

        After a turn the product asks the model behind ``fast`` what to remember. With
        ``script_set`` left alone the stand-in answers from :data:`MEMORY_SCRIPTS`; a test
        that wants other answers loads its own set with :meth:`script` and names it here.
        The store must allow loopback provider URLs. Calling it twice changes nothing.
        """
        platform = tenant_id is None
        if script_set == MEMORY_SET and not self.app.state.scripts.has(MEMORY_SET):
            self.script(MEMORY_SET, MEMORY_SCRIPTS)
        name = f"stand-in-{script_set}"
        provider = _owned(store.providers, tenant_id, "name", name)
        if provider is None:
            provider = store.create_provider(
                tenant_id, name, "openai_compatible", self.base_url(script_set), platform=platform
            )
        model = next(
            (
                row
                for row in store.models.values()
                if row.get("provider_id") == provider["id"]
                or str(row.get("provider_id")) == str(provider["id"])
            ),
            None,
        )
        if model is None:
            model = store.create_model(
                tenant_id,
                uuid.UUID(str(provider["id"])),
                MEMORY_MODEL,
                MEMORY_MODEL,
                "chat",
                platform=platform,
            )
        model_id = uuid.UUID(str(model["id"]))
        alias = _owned(store.aliases, tenant_id, "alias", "fast")
        if alias is None:
            store.create_alias(tenant_id, "fast", "chat", model_id, platform=platform)
        elif alias.get("primary_model_id") != model_id:
            # The row is changed in place: ``update_alias`` also re-runs gated eval suites,
            # which is not what registering a test model is about.
            alias["primary_model_id"] = model_id
        return model_id

    async def save_embeddings(self, store: Any, tenant_id: uuid.UUID) -> uuid.UUID:
        """Register the embedding models for a tenant and save them to the store's database.

        A store attached to a database takes its registry from that database, so rows
        held in memory alone are gone at its next refresh. This saves them the way the
        Models screen does.
        """
        store.allow_loopback = True
        model_id = self.connect_embeddings(store, tenant_id)
        await _save(store, tenant_id)
        return model_id

    async def save_chat(
        self,
        store: Any,
        tenant_id: uuid.UUID,
        *,
        script_set: str,
        aliases: tuple[str, ...] = ("reasoning", "fast"),
    ) -> uuid.UUID:
        """Register the stand-in as the tenant's chat model and save it to the database."""
        store.allow_loopback = True
        model_id = self.connect(store, tenant_id, script_set=script_set, aliases=aliases)
        await _save(store, tenant_id)
        return model_id

    def close(self) -> None:
        self._server.stop()


async def _save(store: Any, tenant_id: uuid.UUID) -> None:
    """Write the tenant's stand-in providers, their models and the aliases that use them."""
    from ar_domain.models import registry  # noqa: PLC0415

    who = {"actor_id": str(tenant_id), "actor_type": "system"}
    engine = store.durable_engine
    providers = {
        key: row
        for key, row in store.providers.items()
        if row.get("tenant_id") == tenant_id and str(row.get("name")).startswith("stand-in-")
    }
    for row in providers.values():
        await registry.save_provider(engine, row, api_key=None, **who)
    models = {key: row for key, row in store.models.items() if row.get("provider_id") in providers}
    for row in models.values():
        await registry.save_model(engine, row, **who)
    for row in list(store.aliases.values()):
        if row.get("tenant_id") == tenant_id and row.get("primary_model_id") in models:
            await registry.save_alias(engine, row, **who)


def _owned(
    rows: dict[uuid.UUID, dict[str, object]], tenant_id: uuid.UUID | None, field: str, value: str
) -> dict[str, object] | None:
    for row in rows.values():
        if row.get("tenant_id") == tenant_id and row.get(field) == value:
            return row
    return None


_shared: list[StandIn] = []


def shared() -> StandIn:
    """One stand-in for the whole process, started on first use.

    It serves from a daemon thread and stops with the process, so code that builds a
    demo tenant outside a pytest session (the browser-test harness) can use it too.
    """
    if not _shared:
        _shared.append(StandIn())
    return _shared[0]


@pytest.fixture(scope="session")
def stand_in() -> Iterator[StandIn]:
    """A scripted model server shared by the session. Give each test its own script set."""
    server = StandIn()
    yield server
    server.close()


@pytest.fixture(scope="session", autouse=True)
def _stand_in_started_first() -> None:
    """Start the shared stand-in before any test runs.

    Some tests replace ``uvicorn.Server`` or ``asyncio.run`` for the process while they
    run. A server that first started inside one of them would not start at all.
    """
    shared()
