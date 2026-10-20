"""Liveness, readiness and metrics routes."""

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse, Response

from ar_common.metrics import metrics_content_type, render_metrics

if TYPE_CHECKING:
    from fastapi import FastAPI

ReadinessCheck = Callable[[], Awaitable[None] | None]


def install_health(app: FastAPI, checks: Mapping[str, ReadinessCheck]) -> None:
    """Add ``/healthz``, ``/readyz`` and ``/metrics``."""

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
        if failing:
            return JSONResponse(
                {"status": "not_ready", "failing": failing},
                status_code=503,
            )
        return JSONResponse({"status": "ready"})

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=render_metrics(), media_type=metrics_content_type())
