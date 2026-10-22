"""Authenticate, tenant guard, CSRF and rate limit. Spec: docs/03-specs/01-api-bff.md §4."""

from starlette.types import ASGIApp, Receive, Scope, Send

from ar_api.auth.csrf import csrf_ok, origin_ok
from ar_api.principal import classify_authorization
from ar_common.errors import ArError, ErrorCode, UnauthenticatedError
from ar_common.web.problems import problem_response

_PUBLIC = frozenset(
    {
        "/api/v1/meta",
        "/api/v1/auth/login",
        "/api/v1/auth/dev-login",
        "/api/v1/auth/callback",
        "/api/v1/.well-known/jwks.json",
        "/api/v1/signup",
        "/healthz",
        "/readyz",
        "/metrics",
        "/docs",
        "/api/docs",
        "/openapi.json",
        "/internal/v1/opa/bundles/ar.tar.gz",
    }
)
_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def is_public(path: str) -> bool:
    """Routes that do not require a principal."""
    if path in _PUBLIC or path.startswith("/api/docs"):
        return True
    if path.startswith("/api/v1/hooks/routines/"):
        return True
    if path == "/api/v1/widget/sessions" or path.startswith("/api/v1/widget/integrations/"):
        return True
    return path.startswith("/api/v1/invitations/") and path.endswith(":accept")


class AuthenticateMiddleware:
    """Resolve a principal and reject anonymous callers on private routes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        scope.setdefault("state", {})
        path = str(scope.get("path", ""))
        resolver = scope["app"].state.resolve_principal
        principal = await resolver(scope)
        if principal is None and not is_public(path):
            response = problem_response(
                UnauthenticatedError(),
                instance=path,
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        if principal is not None and not _tenant_allowed(principal, path):
            response = problem_response(
                ArError(ErrorCode.TENANT_SUSPENDED, "tenant is suspended"),
                instance=path,
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        if principal is not None and getattr(principal, "user_status", "active") not in {
            "active",
            "invited",
        }:
            response = problem_response(
                ArError(ErrorCode.FORBIDDEN, "user is not active"),
                instance=path,
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        scope["state"]["principal"] = principal
        await self.app(scope, receive, send)


class CsrfMiddleware:
    """Session-authenticated unsafe requests must present the CSRF token."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in _UNSAFE:
            await self.app(scope, receive, send)
            return
        # Public routes stay usable with a leftover session cookie. The dev
        # sign-in form switches users and does not carry the previous token.
        if is_public(str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return
        state = scope.get("state", {})
        principal = state.get("principal") if isinstance(state, dict) else None
        if principal is None or getattr(principal, "auth_method", "") != "session":
            await self.app(scope, receive, send)
            return
        header = _header(scope, b"x-csrf-token")
        origin = _header(scope, b"origin")
        public_url = str(
            getattr(scope["app"].state.settings, "public_url", "http://localhost:3000")
        )
        if not csrf_ok(header, getattr(principal, "csrf_token", None)) or not origin_ok(
            origin, public_url
        ):
            response = problem_response(
                ArError(ErrorCode.CSRF_FAILED, "CSRF check failed"),
                instance=str(scope.get("path", "")),
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Per-principal token bucket. Anonymous and public routes are not counted."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.get("state", {})
        principal = state.get("principal") if isinstance(state, dict) else None
        path = str(scope.get("path", ""))
        if principal is None or is_public(path):
            await self.app(scope, receive, send)
            return
        limiter = scope["app"].state.rate_limiter
        limit = int(getattr(scope["app"].state, "rate_limit", 600))
        decision = await limiter.take(f"{principal.tenant_id}:{principal.id}", limit)
        if not decision.allowed:
            response = problem_response(
                ArError(ErrorCode.RATE_LIMITED, "rate limit exceeded"),
                instance=path,
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return

        async def send_limits(message: dict[str, object]) -> None:
            if message["type"] == "http.response.start":
                raw_headers = message.get("headers", [])
                headers = list(raw_headers) if isinstance(raw_headers, list) else []
                headers.extend(
                    (
                        (b"ratelimit-limit", str(decision.limit).encode()),
                        (b"ratelimit-remaining", str(decision.remaining).encode()),
                        (b"ratelimit-reset", str(decision.reset_s).encode()),
                    )
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_limits)  # type: ignore[arg-type]


def presented_credential(scope: Scope) -> tuple[str, str] | None:
    """Return the credential kind and value, if the request has one."""
    header = _header(scope, b"authorization")
    cookie = _cookie(scope, "ar_session")
    found = classify_authorization(header, cookie)
    if found is None:
        return None
    return found.kind, found.value


def _tenant_allowed(principal: object, path: str) -> bool:
    status = getattr(principal, "tenant_status", "active")
    if status == "active":
        return True
    kind = getattr(principal, "kind", "")
    return kind == "platform_admin" and path.startswith("/api/v1/platform/")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return str(value.decode())
    return None


def _cookie(scope: Scope, name: str) -> str | None:
    raw = _header(scope, b"cookie")
    if not raw:
        return None
    for part in raw.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return None


def _request_id(scope: Scope) -> str:
    state = scope.get("state", {})
    if isinstance(state, dict) and isinstance(state.get("request_id"), str):
        return str(state["request_id"])
    return ""
