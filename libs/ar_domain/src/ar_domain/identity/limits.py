"""Plan-limit checks for tenant settings. Spec: docs/03-specs/02-identity-tenancy.md §3.10."""

import re

from pydantic.alias_generators import to_snake

from ar_common.errors import PlanLimitReachedError, ValidationFailedError
from ar_contracts.tenants import PlanLimits, TenantSettings
from ar_domain.identity.plan_limits import LimitContext, check

_DOMAIN = re.compile(
    r"^(\*\.)?[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?)+$"
)


def validate_tenant_settings(settings: TenantSettings, limits: PlanLimits) -> TenantSettings:
    """Reject retention and features the plan does not allow."""
    retention = settings.retention
    ctx = LimitContext(limits, {})
    check(ctx, "max_retention.conversations_days", retention.conversations_days)
    check(ctx, "max_retention.audit_years", retention.audit_years)
    for domain in settings.egress_allowlist:
        if _DOMAIN.fullmatch(domain) is None:
            raise ValidationFailedError(f"egress domain is invalid: {domain}")
    plan_features = limits.features.model_dump(by_alias=False)
    for name, enabled in settings.features.model_dump(by_alias=False).items():
        if enabled and name in plan_features and not plan_features[name]:
            raise PlanLimitReachedError(f"feature {name} is not on this plan")
    return settings


def merge_settings(current: TenantSettings, patch: dict[str, object]) -> TenantSettings:
    """Deep-merge a partial settings document."""
    merged = current.model_dump(by_alias=False)
    _merge(merged, snakeize(patch))
    return TenantSettings.model_validate(merged)


def _snake_key(key: str) -> str:
    return key if "_" in key else to_snake(key)


def snakeize(value: dict[str, object]) -> dict[str, object]:
    """Map public camelCase keys onto the snake_case document stored in JSONB."""
    rewritten: dict[str, object] = {}
    for key, item in value.items():
        name = _snake_key(str(key))
        if isinstance(item, dict):
            rewritten[name] = snakeize(item)
        elif isinstance(item, list):
            rewritten[name] = [
                snakeize(entry) if isinstance(entry, dict) else entry for entry in item
            ]
        else:
            rewritten[name] = item
    return rewritten


def _merge(base: dict[str, object], patch: dict[str, object]) -> None:
    for key, value in patch.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge(current, value)
        else:
            base[key] = value
