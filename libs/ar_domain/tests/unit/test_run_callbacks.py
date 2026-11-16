"""Run callbacks are signed and do not block the caller."""

from __future__ import annotations

import asyncio

from ar_domain.runs.callbacks import _send, deliver_callback


def test_a_refused_callback_is_recorded_without_a_dial() -> None:
    item: dict[str, object] = {
        "url": "http://169.254.169.254/hook",
        "run_id": "run-1",
        "status": "completed",
    }
    _send(item, [], "secret")
    assert item["result"] == "denied"


def test_a_sent_callback_carries_a_signature(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: dict[str, object] = {}

    class _Response:
        status_code = 204

    class _Client:
        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, url: str, content: bytes, headers: dict[str, str]) -> _Response:
            seen["url"] = url
            seen["body"] = content
            seen["signature"] = headers["X-Signature"]
            return _Response()

    monkeypatch.setattr("ar_domain.runs.callbacks.sync_client", lambda **_kwargs: _Client())
    item: dict[str, object] = {
        "url": "https://hooks.example/run",
        "run_id": "run-1",
        "status": "ok",
    }
    _send(item, ["hooks.example"], "top-secret")
    assert item["result"] == "sent"
    assert str(seen["signature"]).startswith("t=")
    assert b"run-1" in seen["body"]  # type: ignore[operator]


def test_delivery_outside_a_loop_uses_a_thread() -> None:
    import time

    item: dict[str, object] = {
        "url": "http://169.254.169.254/hook",
        "run_id": "run-3",
        "status": "completed",
    }
    deliver_callback(type("Store", (), {})(), item)
    for _ in range(50):
        if item.get("result"):
            break
        time.sleep(0.02)
    assert item["result"] == "denied"


def test_delivery_is_scheduled_off_the_caller() -> None:
    async def _run() -> None:
        item: dict[str, object] = {
            "url": "http://169.254.169.254/hook",
            "run_id": "run-2",
            "status": "completed",
        }
        store = type("Store", (), {"callback_tasks": [], "run_callback_secret": "s"})()
        deliver_callback(store, item)
        assert store.callback_tasks
        await store.callback_tasks[0]
        assert item["result"] == "denied"

    asyncio.run(_run())
