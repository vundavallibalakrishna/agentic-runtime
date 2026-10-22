"""One plan-limit check for every creation path.

Spec: docs/03-specs/02-identity-tenancy.md §3.10 and §6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ar_common.errors import ForbiddenError, PlanLimitReachedError
from ar_contracts.tenants import PlanFeatures, PlanLimits

if TYPE_CHECKING:
    from typing import Any

_GIB = 1024 * 1024 * 1024
_CEILINGS = frozenset({"max_sandbox_cpu_millis", "max_sandbox_memory_mb"})


@dataclass(frozen=True, slots=True)
class LimitContext:
    """The plan document and the current usage of each count key."""

    limits: PlanLimits
    counts: dict[str, int]


def limit_keys() -> tuple[str, ...]:
    """Every PlanLimits key a creation path must pass through :func:`check`."""
    keys: list[str] = []
    for name in PlanLimits.model_fields:
        if name in {"unit_prices", "monthly_cost_micros"}:
            continue
        if name == "features":
            keys.extend(f"features.{item}" for item in PlanFeatures.model_fields)
            continue
        if name == "max_retention":
            keys.extend(f"max_retention.{item}" for item in ("conversations_days", "audit_years"))
            continue
        keys.append(name)
    return tuple(keys)


def load_limits(store: Any, tenant_id: object) -> PlanLimits:
    """Plan stored on the tenant, or the spec defaults."""
    raw = _settings(store, tenant_id).get("plan_limits")
    if isinstance(raw, dict):
        return PlanLimits.model_validate(raw)
    return PlanLimits()


def explicit_plan(store: Any, tenant_id: object) -> bool:
    """True when this tenant has a plan document, not only the defaults."""
    return isinstance(_settings(store, tenant_id).get("plan_limits"), dict)


def check(ctx: LimitContext, limit_key: str, delta: int = 1) -> None:
    """Raise when ``delta`` would pass a plan cap or a feature is off.

    Count keys use ``counts[key] + delta``. Ceilings compare ``delta`` with the cap.
    ``features.*`` raises 403 ``feature_not_in_plan:<feature>``. Other keys raise
    409 ``plan_limit_reached`` whose detail is the key.
    """
    if limit_key.startswith("features."):
        _feature(ctx, limit_key.removeprefix("features."))
        return
    if limit_key.startswith("max_retention."):
        _retention(ctx, limit_key.removeprefix("max_retention."), delta)
        return
    if limit_key == "max_storage_gb":
        _storage(ctx, delta)
        return
    if limit_key in _CEILINGS:
        _ceiling(ctx, limit_key, delta)
        return
    cap = getattr(ctx.limits, limit_key, None)
    if cap is None:
        return
    if not isinstance(cap, int):
        raise PlanLimitReachedError(limit_key)
    used = ctx.counts.get(limit_key, 0)
    if used + delta > cap:
        raise PlanLimitReachedError(limit_key)


def guard(
    store: Any,
    tenant_id: object,
    limit_key: str,
    delta: int = 1,
    *,
    current: int = 0,
) -> None:
    """Load the tenant plan and :func:`check` it."""
    check(LimitContext(load_limits(store, tenant_id), {limit_key: current}), limit_key, delta)


def _settings(store: Any, tenant_id: object) -> dict[str, object]:
    settings = getattr(store, "tenant_settings", {})
    if not isinstance(settings, dict):
        return {}
    raw = settings.get(tenant_id)
    if isinstance(raw, dict):
        return raw
    return {}


def _feature(ctx: LimitContext, name: str) -> None:
    enabled = getattr(ctx.limits.features, name, False)
    if not enabled:
        raise ForbiddenError(f"feature_not_in_plan:{name}")


def _retention(ctx: LimitContext, field: str, requested: int) -> None:
    cap = getattr(ctx.limits.max_retention, field, None)
    if not isinstance(cap, int) or requested > cap:
        raise PlanLimitReachedError(f"max_retention.{field}")


def _ceiling(ctx: LimitContext, key: str, requested: int) -> None:
    cap = getattr(ctx.limits, key, None)
    if isinstance(cap, int) and requested > cap:
        raise PlanLimitReachedError(key)


def _storage(ctx: LimitContext, extra_bytes: int) -> None:
    cap = ctx.limits.max_storage_gb
    if cap is None:
        return
    used = ctx.counts.get("max_storage_gb", 0)
    if used + extra_bytes > cap * _GIB:
        raise PlanLimitReachedError("max_storage_gb")
