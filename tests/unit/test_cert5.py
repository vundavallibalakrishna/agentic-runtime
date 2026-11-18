"""Regressions from live certification run 5."""

from __future__ import annotations

import importlib.util
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import orjson
import pytest

from ar_common.egress_http import EgressDenied
from ar_common.internal_http import (
    client_for,
    is_internal_service,
    post,
    tenant_loopback_denied,
    tenant_supplied_url_denied,
)
from ar_common.json_api import camelize, dumps

_CHECK = Path(__file__).resolve().parents[2] / "scripts" / "check_no_fake_models.py"
_SPEC = importlib.util.spec_from_file_location("check_no_fake_models", _CHECK)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
PATTERN = _MODULE.PATTERN


def test_only_a_configured_endpoint_is_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_OPA_URL", "http://opa:8181")
    monkeypatch.delenv("AR_MCP_GATEWAY_URL", raising=False)
    assert is_internal_service("http://opa:8181/v1/data")
    assert not is_internal_service("http://opa:8182/v1")
    assert not is_internal_service("https://opa:8181/v1")
    assert not is_internal_service("http://mcp-gateway:8002/internal/v1")
    assert tenant_supplied_url_denied("http://opa:8181/v1")
    assert tenant_supplied_url_denied("http://opa:9/v1")
    assert tenant_supplied_url_denied("http://mcp-gateway:8002/internal/v1")
    assert tenant_supplied_url_denied("https://example.com/v1") is None


def test_staging_refuses_a_loopback_provider_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_common.settings import EnvName

    monkeypatch.setattr(
        "ar_common.settings.get_settings", lambda: SimpleNamespace(env=EnvName.STAGING)
    )
    from ar_domain.models.logic import provider_url_denied

    deny = ("127.0.0.0/8",)
    assert provider_url_denied("http://127.0.0.1:28000/v1", deny, allow_loopback=True)
    assert tenant_loopback_denied("http://127.0.0.1:28000/v1")


def test_a_supplied_url_is_not_signed_or_dialed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_OPA_URL", "http://opa:8181")
    monkeypatch.setattr("ar_common.egress_http.resolve_host", lambda _host: ["10.0.0.8"])
    with pytest.raises(EgressDenied):
        client_for("http://opa:8181/v1", supplied=True)
    with pytest.raises(EgressDenied):
        post("http://mcp-gateway:8002/internal/v1", supplied=True, timeout=0.2)


def test_public_json_encodes_asyncpg_values() -> None:
    from asyncpg.pgproto import pgproto

    row_id = pgproto.UUID("00112233-4455-6677-8899-aabbccddeeff")
    assert type(row_id).__module__.startswith("asyncpg")
    page = {
        "items": [
            {
                "run_id": row_id,
                "at": datetime(2026, 11, 18, 15, 4, tzinfo=UTC),
                "amount": Decimal("12.50"),
            }
        ],
        "next_cursor": None,
    }
    loaded = orjson.loads(dumps(camelize(page)))
    assert loaded["items"][0]["runId"] == "00112233-4455-6677-8899-aabbccddeeff"
    assert loaded["items"][0]["amount"] == "12.50"
    with pytest.raises(TypeError):
        orjson.dumps(page)


def test_the_fake_model_check_catches_the_removed_eval_script() -> None:
    sample = '"""Eval gym contract check against a local OpenAI-compatible stub.'
    assert PATTERN.search(sample)
    assert PATTERN.search("from ar_domain.evals.harness import stub_reply")


async def test_a_failed_flush_is_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_api.middleware.read_model import ReadModelMiddleware
    from ar_domain.readmodel.model import RepositoryReadModel

    model = RepositoryReadModel(database_url="postgresql+asyncpg://unused/db")

    @asynccontextmanager
    async def opened(*_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        yield SimpleNamespace()

    model.open = opened  # type: ignore[method-assign]

    async def boom(_unit: object) -> None:
        raise RuntimeError("tags")

    monkeypatch.setattr("ar_api.middleware.read_model.commit_unit", boom)

    async def inner(scope: object, receive: object, send: object) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 201, "headers": []})  # type: ignore[operator]
        await send({"type": "http.response.body", "body": b"created"})  # type: ignore[operator]

    sent: list[dict[str, object]] = []

    async def capture(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "path": "/api/v1/eval-suites",
        "app": SimpleNamespace(state=SimpleNamespace(chat=model)),
        "state": {
            "principal": SimpleNamespace(tenant_id=uuid.uuid4(), id="user"),
            "request_id": "req",
        },
    }
    await ReadModelMiddleware(inner)(scope, None, capture)  # type: ignore[arg-type]
    assert sent[0]["status"] == 500
    body = b"".join(
        bytes(message.get("body") or b"")
        for message in sent
        if message.get("type") == "http.response.body"
    )
    assert b"created" not in body
    assert b"could not be saved" in body


def test_run_details_read_the_model_from_the_reply() -> None:
    from ar_testing.demo import demo_store
    from ar_testing.demo_people import DEV_TENANT_ID

    store = demo_store()
    run_id = uuid.uuid4()
    tenant = DEV_TENANT_ID
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "status": "completed",
        "agent_id": uuid.uuid4(),
    }
    store.messages[uuid.uuid4()] = {
        "id": uuid.uuid4(),
        "run_id": run_id,
        "role": "assistant",
        "answered_model": "Qwen3-32B",
        "created_at": "2026-11-18T15:11:53+00:00",
    }
    body = store.get_run(tenant, run_id)
    assert body["answered_model"] == "Qwen3-32B"
