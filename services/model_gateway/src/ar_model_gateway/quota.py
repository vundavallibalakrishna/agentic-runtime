"""Quota gate in front of a chat completion. Spec 17 §2.2."""

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from ar_common.errors import QuotaExceededError
from ar_domain.usage.service import UsageBook


def guard_model_call(request: Request) -> JSONResponse | None:
    """Block when the process store has a chat catalogue and the caller is over quota."""
    store = getattr(request.app.state, "chat", None)
    raw = request.headers.get("x-ar-tenant-id")
    if store is None or not raw:
        return None
    try:
        tenant_id = uuid.UUID(raw)
    except ValueError:
        return None
    try:
        UsageBook(store).assert_model(
            tenant_id,
            request.headers.get("x-ar-user-id"),
            request.headers.get("x-ar-agent-id"),
        )
    except QuotaExceededError as exc:
        problem = exc.to_problem(instance=request.url.path, request_id="")
        return JSONResponse(problem, status_code=429)
    return None
