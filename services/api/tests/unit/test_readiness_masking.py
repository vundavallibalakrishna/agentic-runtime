"""/readyz holds a process out of service until the masking engine is built."""

import asyncio

import pytest

from ar_api import readiness
from ar_domain.pii import analyzer


def test_masking_is_one_of_the_readiness_checks() -> None:
    assert readiness.readiness_names(shared=False) == ["postgres", "temporal", "masking"]
    assert readiness.readiness_names(shared=True) == ["postgres", "valkey", "temporal", "masking"]


def test_not_ready_while_the_engine_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analyzer, "_engine_cache", [])
    with pytest.raises(RuntimeError, match="still loading"):
        asyncio.run(readiness.masking_ready())
    monkeypatch.setattr(analyzer, "_engine_cache", [object()])
    asyncio.run(readiness.masking_ready())
