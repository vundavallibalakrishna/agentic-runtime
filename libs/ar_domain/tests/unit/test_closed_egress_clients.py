"""Probes, token URLs, and cloud OCR use the same closed-egress decision."""

from __future__ import annotations

import uuid

import httpx
import pytest

from ar_common.errors import ArError
from ar_common.settings import get_settings, set_settings
from ar_domain.connectors.catalog import connector_by_slug
from ar_domain.connectors.http import probe_http
from ar_domain.documents.ocr_cloud import read_cloud
from ar_domain.tools.service_connections import _client_credentials


def _closed() -> None:
    set_settings(
        get_settings().model_copy(
            update={"egress_closed": True, "egress_allow_named_private": True}
        )
    )


def test_a_probe_reaches_a_named_private_host_and_refuses_the_rest(monkeypatch) -> None:
    previous = get_settings()
    _closed()
    tenant = uuid.uuid4()
    store = type("Store", (), {})()
    store.connector_transport = httpx.MockTransport(  # type: ignore[attr-defined]
        lambda _request: httpx.Response(200, json={"ok": True})
    )
    connector = connector_by_slug("github")
    assert connector is not None
    try:
        denied = probe_http(store, connector, {}, "https://api.github.com", tenant_id=tenant)
        assert denied["ok"] is False
        assert "allow list" in str(denied["error"])
        store.tenant_settings = {tenant: {"egress_allowlist": ["10.0.0.0/8"]}}  # type: ignore[attr-defined]
        wide = probe_http(store, connector, {}, "http://10.1.2.3", tenant_id=tenant)
        assert wide["ok"] is False
        store.tenant_settings = {tenant: {"egress_allowlist": ["10.1.2.3"]}}  # type: ignore[attr-defined]
        allowed = probe_http(store, connector, {}, "http://10.1.2.3", tenant_id=tenant)
        assert allowed["ok"] is True
        store.tenant_settings = {  # type: ignore[attr-defined]
            tenant: {"egress_allowlist": ["169.254.169.254"]}
        }
        meta = probe_http(store, connector, {}, "http://169.254.169.254", tenant_id=tenant)
        assert meta["ok"] is False
        assert "metadata" in str(meta["error"])
    finally:
        set_settings(previous)
        del monkeypatch


def test_a_token_url_uses_the_tenant_allowlist() -> None:
    previous = get_settings()
    _closed()
    tenant = uuid.uuid4()
    store = type("Store", (), {})()
    row: dict[str, object] = {
        "tenant_id": tenant,
        "name": "okta",
        "token_url": "https://okta.example/oauth/token",
        "client_id": "client",
        "secret": b"",
    }
    try:
        with pytest.raises(ArError, match="allow list"):
            _client_credentials(store, row)
        store.tenant_settings = {tenant: {"egress_allowlist": ["10.4.4.4"]}}  # type: ignore[attr-defined]
        row["token_url"] = "https://10.4.4.4/oauth/token"  # noqa: S105
        row["_token_transport"] = httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"access_token": "minted", "expires_in": "60"}
            )
        )
        tokens = _client_credentials(store, row)
        assert tokens["access_token"] == "minted"  # noqa: S105
    finally:
        set_settings(previous)


def test_cloud_ocr_stays_inside_closed_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    previous = get_settings()
    _closed()
    tenant = uuid.uuid4()
    store = type("Store", (), {})()
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"text": "page"}))
    monkeypatch.setattr(
        "ar_domain.documents.ocr_cloud.read_named_secret",
        lambda *_args, **_kwargs: "http://10.9.9.9/process",
    )
    try:
        assert read_cloud(store, tenant, "google_document_ai", b"page", transport=transport) is None
        store.tenant_settings = {tenant: {"egress_allowlist": ["10.9.9.9"]}}  # type: ignore[attr-defined]
        read = read_cloud(store, tenant, "google_document_ai", b"page", transport=transport)
        assert read is not None
        assert read["text"] == "page"
    finally:
        set_settings(previous)
