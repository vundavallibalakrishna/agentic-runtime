"""The demo tenant: test data for unit tests and the browser-test harness.

A product store starts with no tenant; its tenant, people and agents are rows in its
database. Tests need a tenant without a database, so they build one here: the demo
tenant with its four people, example agents, fixtures and sample review queue.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def demo_store(**options: Any) -> Any:
    """A product store holding the demo tenant. ``options`` go to ``ChatService``."""
    from ar_domain.chat.service import ChatService  # noqa: PLC0415

    store = ChatService(**options)
    store.seed_demo_tenant()
    return store


def demo_application() -> Any:
    """The API application over the demo tenant and its example conversations."""
    from ar_api.main import create_application  # noqa: PLC0415

    app = create_application()
    app.state.chat.seed_demo_tenant()
    app.state.chat.seed_showcase()
    return app
