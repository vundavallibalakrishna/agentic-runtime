"""Plan-limit checks for tenant settings. Spec: docs/03-specs/02-identity-tenancy.md §3.10."""

import re

from pydantic import ValidationError
from pydantic.alias_generators import to_snake

from ar_common.errors import PlanLimitReachedError, ValidationFailedError
from ar_contracts.tenants import PlanLimits, TenantSettings
from ar_domain.identity.plan_limits import LimitContext, check

# Callers used to send these at the root. The document stores them under features.
_FEATURE_ROOTS = ("pii_redaction", "document_analysis_redaction")

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
    _check_masking(settings)
    plan_features = limits.features.model_dump(by_alias=False)
    for name, enabled in settings.features.model_dump(by_alias=False).items():
        if enabled and name in plan_features and not plan_features[name]:
            raise PlanLimitReachedError(f"feature {name} is not on this plan")
    return settings


def _check_masking(settings: TenantSettings) -> None:
    """A kind of personal data the product cannot recognise is refused, by name."""
    listed = settings.privacy.redaction_entities
    if listed is None:
        return
    from ar_domain.pii.analyzer import maskable_entities  # noqa: PLC0415

    known = set(maskable_entities())
    unknown = sorted({name for name in listed if name.lower() not in known})
    if unknown:
        raise ValidationFailedError(
            f"These kinds of personal data are not recognised: {', '.join(unknown)}."
        )


_SHOWN = 200


def settings_diff(
    before: dict[str, object], after: dict[str, object], prefix: str = ""
) -> dict[str, object]:
    """Each setting that changed, by its dotted name, with the old and the new value.

    A long text, such as a privacy notice, is cut to its first 200 characters: the record
    says that it changed, not all of what it said.
    """
    changed: dict[str, object] = {}
    for key in sorted({*before, *after}):
        name = f"{prefix}{key}"
        old, new = before.get(key), after.get(key)
        if isinstance(old, dict) and isinstance(new, dict):
            changed.update(settings_diff(old, new, f"{name}."))
        elif old != new:
            changed[name] = {"from": _shown(old), "to": _shown(new)}
    return changed


def _shown(value: object) -> object:
    return value[:_SHOWN] if isinstance(value, str) else value


def merge_settings(current: TenantSettings, patch: dict[str, object]) -> TenantSettings:
    """Deep-merge a partial settings document.

    An unknown key is a validation error (HTTP 422). It is not an unhandled
    exception. A root ``piiRedaction`` value is stored on ``features``.
    """
    merged = current.model_dump(by_alias=False)
    incoming = snakeize(patch)
    _fold_feature_roots(incoming)
    _merge(merged, incoming)
    try:
        return TenantSettings.model_validate(merged)
    except ValidationError as exc:
        raise ValidationFailedError(_validation_message(exc)) from exc


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


def _fold_feature_roots(patch: dict[str, object]) -> None:
    """Move a root redaction flag onto ``features`` without clobbering a nested one."""
    features = patch.get("features")
    bucket = dict(features) if isinstance(features, dict) else {}
    moved = False
    for name in _FEATURE_ROOTS:
        if name not in patch:
            continue
        value = patch.pop(name)
        moved = True
        bucket.setdefault(name, value)
    if moved:
        patch["features"] = bucket


def _validation_message(exc: ValidationError) -> str:
    parts: list[str] = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ()))
        parts.append(f"{loc}: {item.get('msg', 'invalid')}")
    return "; ".join(parts)[:500] or "Settings are not valid."


def _merge(base: dict[str, object], patch: dict[str, object]) -> None:
    for key, value in patch.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge(current, value)
        else:
            base[key] = value
