"""Open a repository unit for one Temporal activity. Dev keeps the bound double."""

from __future__ import annotations

import functools
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypeVar

_UNIT: ContextVar[object | None] = ContextVar("read_unit", default=None)
_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def active_unit() -> object | None:
    """The unit bound for this task, or None when the process double is in use."""
    return _UNIT.get()


def repository_activity(process_store: Callable[[], object]) -> Callable[[_F], _F]:
    """Load Postgres for this activity when the process store is the read model."""

    def decorate(fn: _F) -> _F:
        @functools.wraps(fn)
        async def wrapper(*args: object, **kwargs: object) -> object:
            holder = process_store()
            from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415

            if not isinstance(holder, RepositoryReadModel):
                return await fn(*args, **kwargs)
            payload = args[0] if args else None
            tenant_id = await holder.resolve_tenant(payload)
            if tenant_id is None:
                return await fn(*args, **kwargs)
            async with holder.open(tenant_id) as unit:
                token = _UNIT.set(unit)
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _UNIT.reset(token)

        return wrapper  # type: ignore[return-value]

    return decorate


def payload_uuid(payload: object, key: str) -> uuid.UUID | None:
    """A UUID field on an activity payload."""
    if not isinstance(payload, dict):
        return None
    return _uuid(payload.get(key))


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None
