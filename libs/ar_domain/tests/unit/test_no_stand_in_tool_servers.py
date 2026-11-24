"""The product serves no stand-in tool server.

Found on 24 November 2026: a tool server a customer registered with ``kind=sql`` was
pointed at a handler in ``tools/handlers.py`` that answered every query with three orders
written in the file, and ``kind=openapi`` with no document got made-up pets. The
handlers now live in ``ar_testing`` and are served only where a test registers them.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ar_domain.tools import handlers
from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest

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
