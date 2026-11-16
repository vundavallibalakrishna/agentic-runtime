"""The review's call-site checks: generated HTTP, routes, and residency."""

from __future__ import annotations

import uuid

import pytest

from ar_common.errors import ArError
from ar_common.settings import get_settings, set_settings
from ar_domain.chat.service import ChatService
from ar_domain.loop.routing import replace_routes
from ar_domain.models.embedding import ModelTarget, embed
from ar_domain.tools.http_tools import execute_operation


def _closed() -> None:
    set_settings(get_settings().model_copy(update={"egress_closed": True}))


def test_execute_operation_does_not_allow_its_own_host() -> None:
    previous = get_settings()
    _closed()
    try:
        result = execute_operation(
            type("Store", (), {})(),
            {
                "_operation": {"method": "GET", "url": "https://evil.test/x"},
                "_tenant_id": uuid.uuid4(),
            },
        )
    finally:
        set_settings(previous)
    assert result["code"] == "egress_denied"
    assert "evil.test" in str(result["text"])


def test_saving_a_route_refuses_a_metadata_address() -> None:
    store = type("Store", (), {"tenant_settings": {}})()
    tenant = uuid.uuid4()
    with pytest.raises(ArError, match="metadata"):
        replace_routes(
            store,
            tenant,
            [{"id": "bad", "base_url": "http://169.254.169.254/v1", "model": "x"}],
        )


def test_chat_service_cluster_residency_refuses_a_public_model() -> None:
    store = ChatService()
    tenant = uuid.uuid4()
    store.tenant_profiles[tenant] = {"data_residency": "cluster"}
    with pytest.raises(ArError, match="public"):
        store.create_provider(
            tenant, "local", "openai_compatible", "https://1.2.3.4/v1", platform=False
        )


def test_embed_uses_the_targets_residency() -> None:
    tenant = uuid.uuid4()
    store = type(
        "Store",
        (),
        {"tenant_profiles": {tenant: {"data_residency": "cluster"}}, "tenant_settings": {}},
    )()
    target = ModelTarget(
        model_id=uuid.uuid4(),
        name="embed",
        label="embed",
        base_url="https://1.2.3.4/v1",
        api_key="",
        timeout_s=1.0,
        dimensions=None,
        tenant_id=tenant,
        egress_store=store,
    )
    with pytest.raises(ArError, match="public"):
        embed(target, ["hello"])
