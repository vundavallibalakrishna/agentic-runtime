"""Demo GRC rows are optional. Catalogues still install."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.chat.service import ChatService
from ar_pack_grc.install import demo_rows_enabled, install_dev

if TYPE_CHECKING:
    import pytest


def test_demo_rows_follow_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_GRC_DEMO", raising=False)
    assert demo_rows_enabled() is True
    monkeypatch.setenv("AR_GRC_DEMO", "0")
    assert demo_rows_enabled() is False
    monkeypatch.setenv("AR_GRC_DEMO", "false")
    assert demo_rows_enabled() is False


def _names(store: ChatService) -> list[str]:
    rows = store.records.get("grc_vendors", {})
    return [str(row.get("name") or "") for row in rows.values() if isinstance(row, dict)]


def test_demo_off_does_not_seed_a_vendor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_GRC_DEMO", "0")
    store = ChatService()
    install_dev(store)
    assert "Northwind" not in _names(store)

    store.dev_binding = type(
        "Binding",
        (),
        {"tenant_id": store.agents[next(iter(store.agents))]["tenant_id"], "users": {}},
    )()
    monkeypatch.setenv("AR_GRC_DEMO", "1")
    install_dev(store)
    assert "Northwind" in _names(store)
