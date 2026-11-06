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
    ) -> uuid.UUID:
        """Register the stand-in as the tenant's model and return the model id.

        The store must allow loopback provider URLs, as a development store does.
        """
        provider = store.create_provider(
            tenant_id,
            f"stand-in-{script_set}",
            "openai_compatible",
            self.base_url(script_set),
            platform=False,
            api_key="stand-in",
        )
        model = store.create_model(
            tenant_id,
            uuid.UUID(str(provider["id"])),
            f"stand-in-{script_set}",
            MODEL,
            "chat",
            platform=False,
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

    async def save_embeddings(self, store: Any, tenant_id: uuid.UUID) -> uuid.UUID:
        """Register the embedding models for a tenant and save them to the store's database.

        A store attached to a database takes its registry from that database, so rows
        held in memory alone are gone at its next refresh. This saves them the way the
        Models screen does.
        """
        from ar_domain.models import registry  # noqa: PLC0415

        store.allow_loopback = True
        model_id = self.connect_embeddings(store, tenant_id)
        who = {"actor_id": str(tenant_id), "actor_type": "system"}
        engine = store.durable_engine
        for row in list(store.providers.values()):
            if row.get("tenant_id") == tenant_id and row.get("name") == "stand-in-embeddings":
                await registry.save_provider(engine, row, api_key=None, **who)
        for row in list(store.models.values()):
            if row.get("tenant_id") == tenant_id and row.get("upstream_model") in {
                EMBEDDING_MODEL,
                RERANK_MODEL,
            }:
                await registry.save_model(engine, row, **who)
        for row in list(store.aliases.values()):
            if row.get("tenant_id") == tenant_id and row.get("alias") in {"embed", "rerank"}:
                await registry.save_alias(engine, row, **who)
        return model_id

    def close(self) -> None:
        self._server.stop()


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
