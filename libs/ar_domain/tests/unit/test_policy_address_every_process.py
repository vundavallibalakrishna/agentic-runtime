"""Every process decides policy the same way: the store is told at build time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_common.settings import BaseServiceSettings
from ar_domain.readmodel.boot import build_product_store

if TYPE_CHECKING:
    import pytest


def test_the_store_takes_the_opa_address_from_the_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AR_OPA_URL", "http://opa:8181")
    store = build_product_store(BaseServiceSettings())
    assert store.opa_url == "http://opa:8181"


def test_no_opa_address_means_the_built_in_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_OPA_URL", raising=False)
    store = build_product_store(BaseServiceSettings())
    assert store.opa_url == ""
