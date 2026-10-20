"""Plan-limit checks for tenant settings. Spec: docs/03-specs/02-identity-tenancy.md §3.10."""

import re

from ar_common.errors import PlanLimitReachedError, ValidationFailedError
from ar_contracts.tenants import PlanLimits, TenantSettings

_DOMAIN = re.compile(
    r"^(\*\.)?[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?)+$"
)


def validate_tenant_settings(settings: TenantSettings, limits: PlanLimits) -> TenantSettings:
    """Reject retention and features the plan does not allow."""
    retention = settings.retention
    cap = limits.max_retention
    if retention.conversations_days > cap.conversations_days:
        raise PlanLimitReachedError("conversations retention exceeds the plan")
    if retention.audit_years > cap.audit_years:
        raise PlanLimitReachedError("audit retention exceeds the plan")
    for domain in settings.egress_allowlist:
        if _DOMAIN.fullmatch(domain) is None:
            raise ValidationFailedError(f"egress domain is invalid: {domain}")
    plan_features = limits.features.model_dump()
    for name, enabled in settings.features.model_dump().items():
        if enabled and name in plan_features and not plan_features[name]:
            raise PlanLimitReachedError(f"feature {name} is not on this plan")
    return settings


def merge_settings(current: TenantSettings, patch: dict[str, object]) -> TenantSettings:
    """Deep-merge a partial settings document."""
    merged = current.model_dump()
    _merge(merged, patch)
    return TenantSettings.model_validate(merged)


def _merge(base: dict[str, object], patch: dict[str, object]) -> None:
    for key, value in patch.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge(current, value)
        else:
            base[key] = value
