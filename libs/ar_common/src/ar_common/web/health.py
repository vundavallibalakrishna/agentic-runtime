"""Liveness, readiness and metrics routes."""

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse, Response

from ar_common.metrics import metrics_content_type, render_metrics

if TYPE_CHECKING:
    from fastapi import FastAPI

ReadinessCheck = Callable[[], Awaitable[None] | None]
ReadinessNote = Callable[[], Awaitable[str] | str]


def install_health(
    app: FastAPI,
    checks: Mapping[str, ReadinessCheck],
    notes: Mapping[str, ReadinessNote] | None = None,
) -> None:
    """Add ``/healthz``, ``/readyz`` and ``/metrics``.

    ``notes`` are reported on a ready response and do not change the status code.
    """

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        failing: list[str] = []
        for name, check in checks.items():
            try:
                result = check()
                if result is not None:
                    await result
            except Exception:  # noqa: BLE001 - a check fails closed on any error
                failing.append(name)
        degraded: list[dict[str, str]] = []
        for name, note in (notes or {}).items():
            try:
                detail = note()
                if detail is not None and not isinstance(detail, str):
                    detail = await detail
            except Exception as exc:  # noqa: BLE001 - a note is detail, not a failure
                detail = str(exc)
            if detail:
                degraded.append({"name": name, "detail": str(detail)})
        if failing:
            body: dict[str, object] = {"status": "not_ready", "failing": failing}
            if degraded:
                body["degraded"] = degraded
            return JSONResponse(body, status_code=503)
        ready: dict[str, object] = {"status": "ready"}
        if degraded:
            ready["degraded"] = degraded
        return JSONResponse(ready)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=render_metrics(), media_type=metrics_content_type())
