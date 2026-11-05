"""Unit tests must not inherit a developer OPA URL from .env."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_api.main import Settings, _configure_policy
from ar_domain.chat.service import ChatService

if TYPE_CHECKING:
    import pytest


def test_pytest_ignores_an_opa_url_that_came_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_OPA_URL", raising=False)
    chat = ChatService()
    settings = Settings.model_construct(opa_url="http://127.0.0.1:8181", opa_timeout_ms=200)
    _configure_policy(chat, settings)
    assert chat.opa_url == ""
    assert chat.opa_timeout_ms == 200


def test_an_explicit_opa_url_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_OPA_URL", "http://127.0.0.1:8181")
    chat = ChatService()
    settings = Settings.model_construct(opa_url="http://127.0.0.1:8181", opa_timeout_ms=200)
    _configure_policy(chat, settings)
    assert chat.opa_url == "http://127.0.0.1:8181"
