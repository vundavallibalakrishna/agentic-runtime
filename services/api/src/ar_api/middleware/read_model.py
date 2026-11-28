"""Open one Postgres unit per authenticated request and commit it with the response."""

from typing import Any  # noqa: TC003

import orjson
from starlette.routing import Match
from starlette.types import ASGIApp, Receive, Scope, Send

from ar_common.errors import InternalError
from ar_common.logging import get_logger
from ar_common.web.problems import problem_response
from ar_domain.readmodel.model import RepositoryReadModel, commit_unit

_PROBE_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})
_HOOK_PREFIX = "/api/v1/hooks/routines/"
_WIDGET_FRAME_PREFIX = "/api/v1/widget/integrations/"
_WIDGET_SESSIONS = "/api/v1/widget/sessions"
# A session request is an id and a token. Anything larger is not one.
_SESSION_BODY_MAX = 32_768
_log = get_logger(__name__)


class _CommitFailedError(Exception):
    """The unit could not be saved. The response has not started."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(type(cause).__name__)
        self.cause = cause


async def _named_widget(receive: Receive) -> tuple[str, Receive]:
    """The widget a session request names, and a ``receive`` that gives the body again.

    The body is read here to find whose data to load, and the route reads it after.
    """
    chunks: list[Any] = []
    body = b""
    while True:
        message = await receive()
        chunks.append(message)
        if message["type"] != "http.request":
            break
        part = message.get("body", b"")
        body += part if isinstance(part, bytes) else b""
        if not message.get("more_body") or len(body) > _SESSION_BODY_MAX:
            break
    size = len(body)
    named = ""
    try:
        parsed = orjson.loads(body) if body and size <= _SESSION_BODY_MAX else {}
    except orjson.JSONDecodeError:
        parsed = {}
    if isinstance(parsed, dict):
        named = str(parsed.get("integrationId") or parsed.get("integration_id") or "")
    pending = list(chunks)

    async def again() -> Any:
        if pending:
            return pending.pop(0)
        return await receive()

    return named, again


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
        endpoint = _read_endpoint(scope)
        if getattr(endpoint, "__repository_read__", False):
            await self.app(scope, receive, send)
            return
        state = scope.get("state", {})
        principal = state.get("principal") if isinstance(state, dict) else None
        path = str(scope.get("path") or "")
        tenant_id, receive = await _tenant_of_request(
            chat, getattr(principal, "tenant_id", None), path, receive
        )
        if tenant_id is None:
            await self.app(scope, receive, send)
            return
        user_id = str(getattr(principal, "id", "") or "")
        request_id = ""
        if isinstance(state, dict):
            raw = state.get("request_id")
            request_id = "" if raw is None else str(raw)
        async with chat.open(
            tenant_id,
            user_id=user_id,
            request_id=request_id,
            commit=False,
            projection=getattr(endpoint, "__read_projection__", "tenant"),
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


async def _tenant_of_request(
    chat: RepositoryReadModel, tenant_id: object, path: str, receive: Receive
) -> tuple[object, Receive]:
    """The tenant a request acts for: its principal's, or the one its address names."""
    if tenant_id is None and path.startswith(_HOOK_PREFIX):
        # A routine's webhook has no sign-in. Its address says whose routine it is.
        tenant_id = await chat.tenant_of_hook(path.removeprefix(_HOOK_PREFIX))
    if tenant_id is None and path.startswith(_WIDGET_FRAME_PREFIX):
        # A page framing a widget is not signed in. The widget's id says whose it is.
        tenant_id = await chat.tenant_of_widget(path.removeprefix(_WIDGET_FRAME_PREFIX))
    if tenant_id is None and path == _WIDGET_SESSIONS:
        # Nor is a visitor starting a session. The widget is named in the request.
        named, receive = await _named_widget(receive)
        tenant_id = await chat.tenant_of_widget(named)
    return tenant_id, receive


def _read_endpoint(scope: Scope) -> object | None:
    """Direct repository endpoints own a tenant transaction instead of a hydrated unit."""
    router = getattr(scope["app"], "router", None)
    if router is None:
        endpoint: object = scope.get("endpoint")
        return endpoint
    for route in router.routes:
        # Included FastAPI routers expose compiled contexts (including any prefix).
        # Their outer matches() deliberately omits the selected endpoint.
        contexts = getattr(route, "effective_route_contexts", None)
        for candidate in contexts() if contexts else (route,):
            match, child = candidate.matches(scope)
            if match == Match.FULL:
                selected: object = child.get("endpoint")
                return selected
    return None
