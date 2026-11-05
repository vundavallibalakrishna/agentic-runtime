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

    def close(self) -> None:
        self._server.stop()


@pytest.fixture(scope="session")
def stand_in() -> Iterator[StandIn]:
    """A scripted model server shared by the session. Give each test its own script set."""
    server = StandIn()
    yield server
    server.close()
