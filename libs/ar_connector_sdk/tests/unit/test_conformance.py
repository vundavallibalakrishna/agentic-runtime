"""Conformance passes the examples and fails a broken server."""

import importlib.util
from pathlib import Path

import pytest

from ar_connector_sdk.conformance import conformance_errors
from ar_connector_sdk.context import ContextError, ToolContext, annotations
from ar_connector_sdk.server import ToolServer

_ROOT = Path(__file__).parents[2] / "examples"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_examples_conform_and_file_a_ticket() -> None:
    hello = _load("hello_connector").build()
    tickets = _load("ticketing_server").build()
    assert conformance_errors(hello) == []
    assert conformance_errors(tickets) == []
    context = ToolContext(tenant_id="tenant", user_id="user", token="access")  # noqa: S106
    filed = tickets.call("create_ticket", {"title": "Printer jammed"}, context)
    assert "TCK-" in filed["text"]
    missing = tickets.call("create_ticket", {"title": "No token"}, ToolContext("tenant", "user"))
    assert missing["is_error"] is True


def test_a_broken_server_fails_conformance() -> None:
    server = ToolServer("broken")

    def handler(_arguments: dict[str, object], _context: ToolContext) -> dict[str, object]:
        return {"text": "no"}

    server.tool("ping", "", {"type": "string"}, handler)
    errors = conformance_errors(server)
    assert errors


def test_context_reads_headers_and_scopes() -> None:
    context = ToolContext.from_headers(
        {
            "X-Ar-Tenant-Id": "tenant",
            "X-Ar-User-Id": "user",
            "Authorization": "Bearer access",
            "X-Ar-Scopes": "tools read",
        }
    )
    assert context.token == "access"  # noqa: S105
    assert context.scopes == ("tools", "read")
    context.require_scope("tools")
    with pytest.raises(ContextError):
        ToolContext.from_headers({})
    with pytest.raises(ContextError):
        context.require_scope("admin")
    assert annotations(read_only=True)["readOnlyHint"] is True


def test_server_reports_handler_faults() -> None:
    server = ToolServer("faults")

    def boom(_arguments: dict[str, object], _context: ToolContext) -> dict[str, object]:
        raise RuntimeError("nope")

    def blank(_arguments: dict[str, object], _context: ToolContext) -> dict[str, object]:
        return {"ok": True}

    server.tool("boom", "Boom", {"type": "object"}, boom)
    server.tool("blank", "Blank", {"type": "object"}, blank)
    context = ToolContext(tenant_id="tenant", user_id="user")
    assert server.call("missing", {}, context)["is_error"] is True
    assert server.call("boom", {}, context)["is_error"] is True
    assert server.call("blank", {}, context)["is_error"] is True
    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, context)
    assert listed["result"]["tools"]
    unknown = server.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"}, context)
    assert "error" in unknown
