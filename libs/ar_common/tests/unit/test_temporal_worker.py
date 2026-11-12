import os

from ar_common.temporal_worker import temporal_unavailable_fields, temporal_worker_kwargs


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


def test_temporal_unavailable_fields_are_actionable() -> None:
    # Production-cert defect 12: the worker log named only the exception class. It now says
    # where it tried to reach Temporal, the error detail, and when it will retry.
    fields = temporal_unavailable_fields("127.0.0.1:7234", TimeoutError("deadline"))
    assert fields["address"] == "127.0.0.1:7234"
    assert fields["error"] == "TimeoutError"
    assert fields["detail"] == "deadline"
    assert fields["retry_in_s"] == 5
    assert "127.0.0.1:7234" in str(fields["message"])
    assert "retry" in str(fields["message"]).lower()
