"""HTTP service template. Spec: docs/03-specs/01-api-bff.md sections 1-2."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError

from ar_common.logging import get_logger, setup_logging
from ar_common.settings import unknown_env_names
from ar_common.telemetry import setup as setup_telemetry
from ar_common.web.health import ReadinessCheck, install_health
from ar_common.web.middleware import install_middleware
from ar_common.web.problems import install_problem_handlers

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ar_common.settings import BaseServiceSettings

_log = get_logger(__name__)


def create_app(
    service_name: str,
    settings: BaseServiceSettings,
    routers: Sequence[APIRouter] | None = None,
    readiness_checks: Mapping[str, ReadinessCheck] | None = None,
) -> FastAPI:
    """Build a FastAPI app with request ids, problem responses, health and metrics."""
    setup_logging(settings)
    setup_telemetry(service_name, settings)
    unknown = _unknown(settings)
    for name in unknown:
        _log.warning("unknown_env", name=name)
    app = FastAPI(title=service_name, version="0.1.0")
    app.state.settings = settings
    app.state.service_name = service_name
    install_middleware(app, settings)
    install_problem_handlers(app)
    install_health(app, readiness_checks or {})
    for router in routers or []:
        app.include_router(router)
    _ = RequestValidationError
    return app


def _unknown(settings: BaseServiceSettings) -> list[str]:
    return unknown_env_names(settings)
