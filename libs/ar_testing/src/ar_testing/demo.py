"""The demo tenant: test data for unit tests and the browser-test harness.

A product store starts with no tenant; its tenant, people and agents are rows in its
database, and people sign in through the identity provider. Tests need a tenant without a
database, so they build one here: the demo tenant with its four people, example agents,
fixtures and sample review queue, an identity read from memory, and a way to start a
session for one of those people.
"""

from typing import TYPE_CHECKING

from ar_testing.demo_people import DEV_TENANT_ID, catalogue
from ar_testing.demo_tenant import seed_demo_tenant
from ar_testing.objects import MemoryObjectStore
from ar_testing.showcase_build import seed_showcase

if TYPE_CHECKING:
    from typing import Any


def demo_store(**options: Any) -> Any:
    """A product store holding the demo tenant. ``options`` go to ``ChatService``."""
    from ar_domain.chat.service import ChatService  # noqa: PLC0415

    # Tests reach stand-ins on loopback addresses. A product store refuses them by default.
    options.setdefault("allow_loopback", True)
    # File bytes go to a store in memory; the product's own is the configured S3 bucket.
    options.setdefault("objects", MemoryObjectStore())
    store = ChatService(**options)
    seed_demo_tenant(store)
    connect_embeddings(store)
    return store


def connect_embeddings(store: Any) -> None:
    """Give a store the models memory and knowledge need: the stand-in, reached over HTTP.

    A product store has none until an administrator registers them. Knowledge and memory
    refuse to store anything without an embedding model, and nothing is remembered from a
    turn without a chat model to ask.
    """
    from ar_testing.stand_in import shared  # noqa: PLC0415

    # The stand-in listens on loopback, which a product store refuses by default.
    store.allow_loopback = True
    shared().connect_embeddings(store)
    # After a turn the product asks a model what to remember: the stand-in answers that too.
    shared().connect_extraction(store)


def connect_chat(store: Any, tenant_id: Any) -> None:
    """Point the tenant's ``reasoning`` alias at the stand-in for the browser tests.

    The browser tests run the product's own agent loop against a real model call: the
    stand-in answers from the ``demo-chat`` script set, with the tool flows and answers the
    specs expect. Unmatched turns fall through to the stand-in's default (an echo and the
    ``/tool`` command), so a spec that reads a plain answer still runs a real model call.
    The ``fast`` alias stays on the memory script set (``connect_extraction``).
    """
    from ar_testing.demo_chat import DEMO_CHAT, DEMO_CHAT_SET  # noqa: PLC0415
    from ar_testing.stand_in import shared  # noqa: PLC0415

    store.allow_loopback = True
    server = shared()
    server.script(DEMO_CHAT_SET, DEMO_CHAT)
    # The demo tenant registers the stand-in as its own chat model and points `reasoning` at
    # it, the way a real tenant brings its own model. `fast` stays on the memory set the
    # extraction step uses.
    server.connect(store, tenant_id, script_set=DEMO_CHAT_SET, aliases=("reasoning",))


def serve_demo_tenant(app: Any) -> Any:
    """Make an API application serve the demo tenant from memory.

    The store gets the demo tenant, the application is told which tenant it serves, and
    identity is read from memory in place of the database.
    """
    from ar_domain.durable.bind import TenantBinding  # noqa: PLC0415
    from ar_testing.memory_identity import memory_identity  # noqa: PLC0415

    store = app.state.chat
    # The browser tests run with no object store; file bytes are kept in memory.
    store.objects = MemoryObjectStore()
    seed_demo_tenant(store)
    connect_embeddings(store)
    connect_chat(store, DEV_TENANT_ID)
    seed_showcase(store)
    store.tenant_binding = TenantBinding(
        tenant_id=DEV_TENANT_ID,
        slug="dev",
        name="Dev",
        plan="enterprise",
        users={email: person.user_id for email, person in catalogue().items()},
    )
    app.state.identity_provider = lambda ctx: memory_identity(store, ctx).store
    return app


def demo_application() -> Any:
    """The API application over the demo tenant and its example conversations."""
    from ar_api.main import create_application  # noqa: PLC0415

    return serve_demo_tenant(create_application())


def rebuild_demo_store(app: Any) -> Any:
    """Give a running demo application a freshly seeded store, in place.

    Only the browser-test harness calls this, between a failed attempt and its retry, so a
    retried flow starts from the seeded baseline instead of the rows the failed attempt
    left behind (the harness keeps one in-memory tenant for the whole run, so without this
    a retry would see another copy of what the attempt before it created). It reuses the
    startup build path, so the new store carries the same configuration, and swaps it onto
    the application; every request reads ``app.state.chat`` afresh. Sessions are untouched,
    and the retried test signs in again anyway. A product process has no such door.
    """
    fresh = demo_application()
    app.state.chat = fresh.state.chat
    app.state.identity_provider = fresh.state.identity_provider
    return app


async def start_session(app: Any, email: str) -> dict[str, str]:
    """Start a session for a demo person. Returns the two cookies a browser would hold."""
    from ar_api.auth.session import new_session, remember_profile  # noqa: PLC0415

    person = catalogue()[email.strip().lower()]
    session_id, data = new_session(DEV_TENANT_ID, person.user_id)
    remember_profile(
        data,
        email=person.email,
        display_name=person.display_name,
        roles=list(person.roles),
        permissions=sorted(person.permissions),
    )
    await app.state.sessions.put(session_id, data, int(app.state.settings.session_ttl_s))
    return {"ar_session": session_id, "ar_csrf": data.csrf_token}


KITE_NOTES = {
    "kite-overview.md": (
        "# Kite overview\n\n"
        "A kite flies because the wind pushes on its sail and the line holds it at an angle. "
        "The stored notes say a kite needs steady wind of at least eight knots.\n"
    ),
    "kite-string.md": (
        "# Kite string\n\n"
        "The string of a kite is called the line. The stored notes say a braided line of "
        "thirty metres is enough for a first flight.\n"
    ),
}


def add_library_notes(store: Any) -> list[str]:
    """Put two short notes in the demo tenant's document library, and return their ids.

    Research and document search read the library. A test that needs something to find
    adds these, the way a person uploads documents.
    """
    import asyncio  # noqa: PLC0415

    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.chat.service import demo_id  # noqa: PLC0415
    from ar_domain.documents.library import ingest_bytes  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

    actor = Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)
    ids: list[str] = []
    for name, text in KITE_NOTES.items():
        note = ingest_bytes(
            store, actor, data=text.encode(), filename=name, media_type="text/markdown"
        )
        row = asyncio.run(note)
        ids.append(str(row.get("id") or ""))
    return ids
