import os

from ar_common.temporal_worker import temporal_worker_kwargs


def test_temporal_worker_kwargs_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("TEMPORAL_WORKER_BUILD_ID", raising=False)
    monkeypatch.delenv("TEMPORAL_USE_WORKER_VERSIONING", raising=False)
    assert temporal_worker_kwargs() == {}


def test_temporal_worker_kwargs_requires_both(monkeypatch) -> None:
    monkeypatch.setenv("TEMPORAL_WORKER_BUILD_ID", "1.0.0")
    monkeypatch.delenv("TEMPORAL_USE_WORKER_VERSIONING", raising=False)
    assert temporal_worker_kwargs() == {}


def test_temporal_worker_kwargs_on(monkeypatch) -> None:
    monkeypatch.setenv("TEMPORAL_WORKER_BUILD_ID", " 1.0.0 ")
    monkeypatch.setenv("TEMPORAL_USE_WORKER_VERSIONING", "true")
    assert temporal_worker_kwargs() == {"build_id": "1.0.0", "use_worker_versioning": True}
    assert "TEMPORAL_WORKER_BUILD_ID" in os.environ
