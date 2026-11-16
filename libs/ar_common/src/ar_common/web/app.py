"""HTTP service template. Spec: docs/03-specs/01-api-bff.md sections 1-2."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError

from ar_common.logging import get_logger, setup_logging
from ar_common.settings import unknown_env_names
from ar_common.telemetry import setup as setup_telemetry
from ar_common.web.health import ReadinessCheck, ReadinessNote, install_health
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
    readiness_notes: Mapping[str, ReadinessNote] | None = None,
    *,
    inner_middleware: list[tuple[type, dict[str, object]]] | None = None,
    docs_url: str | None = "/docs",
    camel_json: bool = False,
    body_limits: dict[str, int] | None = None,
) -> FastAPI:
    """Build a FastAPI app with request ids, problem responses, health and metrics."""
    setup_logging(settings)
    setup_telemetry(service_name, settings)
    unknown = _unknown(settings)
    for name in unknown:
        _log.warning("unknown_env", name=name)
    _warn_default_database_password(settings)
    app = FastAPI(title=service_name, version="0.1.0", docs_url=docs_url)
    app.state.settings = settings
    app.state.service_name = service_name
    install_middleware(
        app, settings, inner_middleware, camel_json=camel_json, body_limits=body_limits
    )
    install_problem_handlers(app)
    install_health(app, readiness_checks or {}, readiness_notes)
    for router in routers or []:
        app.include_router(router)
    _ = RequestValidationError
    return app


def _unknown(settings: BaseServiceSettings) -> list[str]:
    return unknown_env_names(settings)


_state = {"password_warned": False}


def _warn_default_database_password(settings: BaseServiceSettings) -> None:
    """The chart ships a public password. An install that keeps it is logged once."""
    url = str(getattr(settings, "database_url", "") or "")
    if _state["password_warned"] or "ar-install-db" not in url:
        return
    _state["password_warned"] = True
    _log.error(
        "default_database_password",
        detail=(
            "AR_DATABASE_URL still uses the chart default password ar-install-db. "
            "Set postgres.password before exposing the install."
        ),
    )
