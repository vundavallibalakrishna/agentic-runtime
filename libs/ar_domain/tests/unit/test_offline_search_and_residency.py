"""SearXNG is a settings value. Cluster residency refuses a public model URL."""

from __future__ import annotations

import uuid

from ar_contracts.tenants import SearchSettings, TenantSettings
from ar_domain.egress import model_refusal
from ar_domain.tools.searching import provider_for


def test_searxng_is_a_search_setting() -> None:
    settings = TenantSettings.model_validate(
        {"search": {"provider": "searxng", "baseUrl": "http://searx.internal"}}
    )
    assert isinstance(settings.search, SearchSettings)
    assert settings.search.provider == "searxng"
    assert settings.search.base_url == "http://searx.internal"


def test_searxng_is_used_when_the_tenant_names_it() -> None:
    tenant = uuid.uuid4()

    store = type("Store", (), {})()
    store.tenant_settings = {  # type: ignore[attr-defined]
        tenant: {"search": {"provider": "searxng", "base_url": "http://searx.internal"}}
    }
    store.search_provider = None  # type: ignore[attr-defined]

    provider = provider_for(store, tenant)
    assert provider._base == "http://searx.internal"  # type: ignore[attr-defined]


def test_cluster_residency_accepts_a_private_model_and_refuses_a_public_one() -> None:
    assert model_refusal(None, None, "http://10.1.2.3:8000/v1", residency="cluster") is None
    public = model_refusal(None, None, "https://1.2.3.4/v1", residency="cluster")
    assert public is not None
    assert "public" in public
    assert model_refusal(None, None, "https://1.2.3.4/v1", residency="in") is None
    meta = model_refusal(None, None, "http://169.254.169.254/", residency="cluster")
    assert meta is not None
    assert "metadata" in meta
