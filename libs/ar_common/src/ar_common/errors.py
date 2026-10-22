"""RFC 9457 problem types. Spec: docs/05-contracts/api-conventions.md §5."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue

PROBLEM_TYPE_BASE = "https://docs.agentic-runtime.dev/errors"


class ErrorCode(StrEnum):
    """Stable client-facing error codes. The set matches api-conventions exactly."""

    BAD_REQUEST = "bad_request"
    INVALID_CURSOR = "invalid_cursor"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    CSRF_FAILED = "csrf_failed"
    TENANT_SUSPENDED = "tenant_suspended"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RUN_IN_PROGRESS = "run_in_progress"
    IDEMPOTENCY_KEY_REUSED = "idempotency_key_reused"
    INVALID_STATE = "invalid_state"
    PLAN_LIMIT_REACHED = "plan_limit_reached"
    PRECONDITION_FAILED = "precondition_failed"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    VALIDATION_FAILED = "validation_failed"
    UNKNOWN_REFERENCE = "unknown_reference"
    PACK_SIGNATURE_INVALID = "pack_signature_invalid"
    EXTENSION_UNAVAILABLE = "extension_unavailable"
    RESOURCE_DISABLED = "resource_disabled"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    INTERNAL_ERROR = "internal_error"
    UPSTREAM_ERROR = "upstream_error"
    UNAVAILABLE = "unavailable"
    UPSTREAM_TIMEOUT = "upstream_timeout"


class FieldError(BaseModel):
    """One validation error entry inside a problem body."""

    model_config = ConfigDict(extra="forbid")

    loc: list[str | int]
    msg: str
    type: str


_SPECS: dict[ErrorCode, tuple[int, str]] = {
    ErrorCode.BAD_REQUEST: (400, "Bad request"),
    ErrorCode.INVALID_CURSOR: (400, "Invalid cursor"),
    ErrorCode.UNAUTHENTICATED: (401, "Unauthenticated"),
    ErrorCode.FORBIDDEN: (403, "Forbidden"),
    ErrorCode.CSRF_FAILED: (403, "CSRF check failed"),
    ErrorCode.TENANT_SUSPENDED: (403, "Tenant suspended"),
    ErrorCode.NOT_FOUND: (404, "Not found"),
    ErrorCode.CONFLICT: (409, "Conflict"),
    ErrorCode.RUN_IN_PROGRESS: (409, "Run in progress"),
    ErrorCode.IDEMPOTENCY_KEY_REUSED: (409, "Idempotency key reused"),
    ErrorCode.INVALID_STATE: (409, "Invalid state"),
    ErrorCode.PLAN_LIMIT_REACHED: (409, "Plan limit reached"),
    ErrorCode.PRECONDITION_FAILED: (412, "Precondition failed"),
    ErrorCode.PAYLOAD_TOO_LARGE: (413, "Payload too large"),
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: (415, "Unsupported media type"),
    ErrorCode.VALIDATION_FAILED: (422, "Validation failed"),
    ErrorCode.UNKNOWN_REFERENCE: (422, "Unknown reference"),
    ErrorCode.PACK_SIGNATURE_INVALID: (422, "Pack signature invalid"),
    ErrorCode.EXTENSION_UNAVAILABLE: (422, "Extension unavailable"),
    ErrorCode.RESOURCE_DISABLED: (423, "Resource disabled"),
    ErrorCode.RATE_LIMITED: (429, "Rate limited"),
    ErrorCode.QUOTA_EXCEEDED: (429, "Quota exceeded"),
    ErrorCode.INTERNAL_ERROR: (500, "Internal error"),
    ErrorCode.UPSTREAM_ERROR: (502, "Upstream error"),
    ErrorCode.UNAVAILABLE: (503, "Unavailable"),
    ErrorCode.UPSTREAM_TIMEOUT: (504, "Upstream timeout"),
}


def http_status_for(code: ErrorCode) -> int:
    """Return the HTTP status mapped to an error code."""
    return _SPECS[code][0]


def title_for(code: ErrorCode) -> str:
    """Return the human title mapped to an error code."""
    return _SPECS[code][1]


class ArError(Exception):
    """Base error mapped to an ``application/problem+json`` body."""

    def __init__(
        self,
        code: ErrorCode,
        detail: str,
        *,
        errors: list[FieldError] | None = None,
        title: str | None = None,
    ) -> None:
        self.code = code
        self.status = http_status_for(code)
        self.title = title if title is not None else title_for(code)
        self.detail = detail
        self.errors = errors or []
        super().__init__(detail)

    def to_problem(self, *, instance: str, request_id: str) -> dict[str, JsonValue]:
        """Build the RFC 9457 body."""
        body: dict[str, JsonValue] = {
            "type": f"{PROBLEM_TYPE_BASE}/{self.code.value}",
            "title": self.title,
            "status": self.status,
            "code": self.code.value,
            "detail": self.detail,
            "instance": instance,
            "requestId": request_id,
        }
        if self.errors:
            body["errors"] = [item.model_dump() for item in self.errors]
        return body


class BadRequestError(ArError):
    def __init__(self, detail: str, *, errors: list[FieldError] | None = None) -> None:
        super().__init__(ErrorCode.BAD_REQUEST, detail, errors=errors)


class InvalidCursorError(ArError):
    def __init__(self, detail: str = "Pagination cursor is invalid") -> None:
        super().__init__(ErrorCode.INVALID_CURSOR, detail)


class UnauthenticatedError(ArError):
    def __init__(self, detail: str = "Authentication is required") -> None:
        super().__init__(ErrorCode.UNAUTHENTICATED, detail)


class ForbiddenError(ArError):
    def __init__(self, detail: str = "You do not have permission to do that") -> None:
        super().__init__(ErrorCode.FORBIDDEN, detail)


class NotFoundError(ArError):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(ErrorCode.NOT_FOUND, detail)


class ConflictError(ArError):
    def __init__(self, detail: str) -> None:
        super().__init__(ErrorCode.CONFLICT, detail)


class ValidationFailedError(ArError):
    def __init__(self, detail: str, *, errors: list[FieldError] | None = None) -> None:
        super().__init__(ErrorCode.VALIDATION_FAILED, detail, errors=errors)


class PayloadTooLargeError(ArError):
    def __init__(self, detail: str = "Request body exceeds the configured limit") -> None:
        super().__init__(ErrorCode.PAYLOAD_TOO_LARGE, detail)


class RateLimitedError(ArError):
    def __init__(self, detail: str = "Rate limit exceeded") -> None:
        super().__init__(ErrorCode.RATE_LIMITED, detail)


class InternalError(ArError):
    def __init__(self, detail: str = "Unexpected error") -> None:
        super().__init__(ErrorCode.INTERNAL_ERROR, detail)


class UnavailableError(ArError):
    def __init__(self, detail: str = "Dependency unavailable") -> None:
        super().__init__(ErrorCode.UNAVAILABLE, detail)


class PlanLimitReachedError(ArError):
    def __init__(self, detail: str) -> None:
        super().__init__(ErrorCode.PLAN_LIMIT_REACHED, detail)


class QuotaExceededError(ArError):
    """429 body includes the quota that blocked the call."""

    def __init__(
        self,
        detail: str,
        *,
        quota_id: str,
        metric: str,
        period: str,
        limit: int,
        used: int,
        resets_at: str,
    ) -> None:
        super().__init__(ErrorCode.QUOTA_EXCEEDED, detail)
        self.quota_id = quota_id
        self.metric = metric
        self.period = period
        self.limit = limit
        self.used = used
        self.resets_at = resets_at

    def to_problem(self, *, instance: str, request_id: str) -> dict[str, JsonValue]:
        body = super().to_problem(instance=instance, request_id=request_id)
        body["quotaId"] = self.quota_id
        body["metric"] = self.metric
        body["period"] = self.period
        body["limit"] = self.limit
        body["used"] = self.used
        body["resetsAt"] = self.resets_at
        return body
