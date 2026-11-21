import os
from datetime import timedelta

from ar_common.settings import get_settings, set_settings
from ar_common.temporal_worker import temporal_unavailable_fields, temporal_worker_kwargs

# A stop reaches an activity with its next report, so every worker reports often.
_REPORTS = {"max_heartbeat_throttle_interval": timedelta(seconds=2)}


def test_temporal_worker_kwargs_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("TEMPORAL_WORKER_BUILD_ID", raising=False)
    monkeypatch.delenv("TEMPORAL_USE_WORKER_VERSIONING", raising=False)
    assert temporal_worker_kwargs() == _REPORTS


def test_temporal_worker_kwargs_requires_both(monkeypatch) -> None:
    monkeypatch.setenv("TEMPORAL_WORKER_BUILD_ID", "1.0.0")
    monkeypatch.delenv("TEMPORAL_USE_WORKER_VERSIONING", raising=False)
    assert temporal_worker_kwargs() == _REPORTS


def test_temporal_worker_kwargs_on(monkeypatch) -> None:
    monkeypatch.setenv("TEMPORAL_WORKER_BUILD_ID", " 1.0.0 ")
    monkeypatch.setenv("TEMPORAL_USE_WORKER_VERSIONING", "true")
    assert temporal_worker_kwargs() == {
        **_REPORTS,
        "build_id": "1.0.0",
        "use_worker_versioning": True,
    }
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


def test_how_often_an_activity_reports_is_a_setting() -> None:
    before = get_settings()
    set_settings(before.model_copy(update={"activity_heartbeat_throttle_s": 5}))
    try:
        assert temporal_worker_kwargs()["max_heartbeat_throttle_interval"] == timedelta(seconds=5)
    finally:
        set_settings(before)
