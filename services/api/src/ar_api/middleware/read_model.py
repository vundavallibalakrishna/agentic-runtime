"""Open one Postgres unit per authenticated request and commit it with the response."""

from starlette.types import ASGIApp, Receive, Scope, Send

from ar_common.errors import InternalError
from ar_common.logging import get_logger
from ar_common.web.problems import problem_response
from ar_domain.readmodel.model import RepositoryReadModel, commit_unit

_PROBE_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})
_log = get_logger(__name__)


class _CommitFailedError(Exception):
    """The unit could not be saved. The response has not started."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(type(cause).__name__)
        self.cause = cause


class ReadModelMiddleware:
    """Repositories per request. A process-local double is left untouched.

    The unit is committed before the response starts. A flush that fails is a
    500 the client receives. It is not a success followed by a dropped connection.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or str(scope.get("path", "")) in _PROBE_PATHS:
            await self.app(scope, receive, send)
            return
        chat = scope["app"].state.chat
        if not isinstance(chat, RepositoryReadModel):
            await self.app(scope, receive, send)
            return
        state = scope.get("state", {})
        principal = state.get("principal") if isinstance(state, dict) else None
        tenant_id = getattr(principal, "tenant_id", None)
        if tenant_id is None:
            await self.app(scope, receive, send)
            return
        user_id = str(getattr(principal, "id", "") or "")
        request_id = ""
        if isinstance(state, dict):
            raw = state.get("request_id")
            request_id = "" if raw is None else str(raw)
        path = str(scope.get("path") or "")
        async with chat.open(
            tenant_id, user_id=user_id, request_id=request_id, commit=False
        ) as unit:
            if isinstance(state, dict):
                state["read_unit"] = unit
            started = False

            async def sending(message: dict[str, object]) -> None:
                nonlocal started
                if message["type"] == "http.response.start" and not started:
                    try:
                        await commit_unit(unit)
                    except Exception as exc:
                        raise _CommitFailedError(exc) from exc
                    started = True
                await send(message)

            try:
                await self.app(scope, receive, sending)  # type: ignore[arg-type]
            except _CommitFailedError as failed:
                _log.error("read_model_commit_failed", error=type(failed.cause).__name__)
                response = problem_response(
                    InternalError("The change could not be saved."),
                    instance=path,
                    request_id=request_id,
                )
                await response(scope, receive, send)
                return
            finally:
                if isinstance(state, dict):
                    state["read_unit"] = None
            if not started:
                await commit_unit(unit)
