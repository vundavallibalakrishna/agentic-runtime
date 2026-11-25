"""The product serves no stand-in tool server.

Found on 24 November 2026: a tool server a customer registered with ``kind=sql`` was
pointed at a handler in ``tools/handlers.py`` that answered every query with three orders
written in the file, and ``kind=openapi`` with no document got made-up pets. The
handlers now live in ``ar_testing`` and are served only where a test registers them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ar_domain.tools import handlers
from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store

_TOOLS = Path(handlers.__file__).parent
_STAND_INS = ("memory://tickets", "memory://echo", "memory://petstore", "memory://warehouse")


def test_an_install_answers_none_of_the_stand_in_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    # An install: nothing has registered an endpoint in this process.
    monkeypatch.setattr(handlers, "_ENDPOINTS", {})
    monkeypatch.setattr(handlers, "_DISCOVERED", {})
    for address in _STAND_INS:
        answer = dispatch(store, address, "run_query", {"sql": "SELECT 1"}, "token")
        assert answer["is_error"] is True
        assert answer["code"] == "upstream_error"
        assert not handlers.endpoint_registered(address)


def test_the_dispatcher_and_the_registry_name_no_stand_in_address() -> None:
    for name in ("handlers.py", "registry.py"):
        source = (_TOOLS / name).read_text(encoding="utf-8")
        assert "memory://" not in source, f"{name} still names an in-memory tool server"


def test_an_install_has_no_database_at_an_in_memory_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A data connection at ``memory://warehouse`` used to answer with three orders."""
    from ar_common.errors import ValidationFailedError
    from ar_domain.agents.access import Actor
    from ar_domain.demo_ids import demo_id
    from ar_domain.tools import database
    from ar_domain.tools.data_connections import DataConnections

    store = demo_store()
    # An install: no pack serves a database in this process.
    monkeypatch.setattr(database, "_SOURCES", {})
    actor = Actor(demo_id("tenant"), demo_id("admin"), frozenset({"tools:create"}))
    with pytest.raises(ValidationFailedError, match="postgresql:// or mysql://"):
        DataConnections(store).create(
            actor, {"name": "ledger", "engine": "postgres", "dsn": "memory://warehouse"}
        )


def test_the_data_tools_name_no_in_memory_address() -> None:
    for name in ("database.py", "data_connections.py"):
        source = (_TOOLS / name).read_text(encoding="utf-8")
        assert "memory:" not in source, f"{name} still treats an in-memory address specially"


def test_no_token_is_made_up_in_the_product() -> None:
    """A token address beginning ``memory://`` used to get a token without a call.

    So did the code ``invalid``, which was refused without one. Both answers were in
    ``credentials.py`` and ``service_connections.py``. A token now comes only from the
    endpoint the provider names.
    """
    for name in ("credentials.py", "service_connections.py"):
        source = (_TOOLS / name).read_text(encoding="utf-8")
        assert "memory://" not in source, f"{name} still answers an in-memory token address"
        assert '"invalid"' not in source, f"{name} still refuses a code by its spelling"


def test_the_product_seed_builds_no_tenant_rows() -> None:
    """``seed_tools.py`` built the demo tenant's servers, agents and settings until 25 Nov 2026."""
    from ar_domain.chat.service import ChatService

    source = (_TOOLS / "seed_tools.py").read_text(encoding="utf-8")
    assert "memory://" not in source
    store = ChatService()
    assert all(row.get("tenant_id") is None for row in store.tool_servers.values())
    assert not store.agents
    assert not store.credential_providers
    assert not store.data_connections
    assert not store.tenant_settings


def test_the_product_catalogue_is_the_same_in_every_environment() -> None:
    """The approval test tool was in the catalogue only where fake models were allowed."""
    from ar_domain.chat.service import ChatService

    def names(store: ChatService) -> set[str]:
        return {str(row["qualified_name"]) for row in store.tool_versions.values()}

    assert "session.propose_change" not in names(ChatService())
    for name in ("seed_tools.py", "handlers.py"):
        source = (_TOOLS / name).read_text(encoding="utf-8")
        assert "propose_change" not in source
        assert "fake_models_allowed" not in source
