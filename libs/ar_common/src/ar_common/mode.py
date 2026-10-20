"""Deployment-mode helpers. Spec: docs/00-overview/deployment-modes.md."""

from ar_common.settings import BaseServiceSettings, DeploymentMode, get_settings


def is_saas(settings: BaseServiceSettings | None = None) -> bool:
    """Return whether this process is running in multi-tenant SaaS mode."""
    current = get_settings() if settings is None else settings
    return current.deployment_mode is DeploymentMode.SAAS


def is_single_tenant(settings: BaseServiceSettings | None = None) -> bool:
    """Return whether this process is a single-tenant install."""
    return not is_saas(settings)
