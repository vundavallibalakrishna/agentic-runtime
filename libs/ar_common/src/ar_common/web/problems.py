"""Map exceptions to RFC 9457 responses."""

from typing import TYPE_CHECKING

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ar_common.errors import ArError, FieldError, InternalError, ValidationFailedError
from ar_common.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI, Request
    from starlette.requests import Request as StarletteRequest

_log = get_logger(__name__)


def problem_response(error: ArError, *, instance: str, request_id: str) -> JSONResponse:
    """Serialise an :class:`ArError` as ``application/problem+json``."""
    return JSONResponse(
        error.to_problem(instance=instance, request_id=request_id),
        status_code=error.status,
        media_type="application/problem+json",
    )


def install_problem_handlers(app: FastAPI) -> None:
    """Register handlers for domain errors, validation errors and unexpected exceptions."""

    @app.exception_handler(ArError)
    async def handle_ar(request: Request, exc: ArError) -> JSONResponse:
        return problem_response(exc, instance=request.url.path, request_id=_request_id(request))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            FieldError(
                loc=[str(part) for part in item["loc"] if part != "body"],
                msg=str(item["msg"]),
                type=str(item["type"]),
            )
            for item in exc.errors()
        ]
        error = ValidationFailedError("Request validation failed", errors=fields)
        return problem_response(error, instance=request.url.path, request_id=_request_id(request))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        _log.error("unhandled_error", error_type=type(exc).__name__, path=request.url.path)
        error = InternalError()
        return problem_response(error, instance=request.url.path, request_id=_request_id(request))


def _request_id(request: StarletteRequest) -> str:
    value = getattr(request.state, "request_id", "")
    return str(value)
