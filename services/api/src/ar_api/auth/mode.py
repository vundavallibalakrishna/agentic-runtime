"""Which sign-in a process offers.

Production is the customer's OIDC provider (ADR-0031). A userid and password
is the dev and single-tenant mode, and it is not the Helm default.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from ar_common.settings import DeploymentMode, EnvName

if TYPE_CHECKING:
    from ar_api.main import Settings


class AuthMode(StrEnum):
    PASSWORD = "password"  # noqa: S105
    OIDC = "oidc"


def resolve_auth_mode(settings: Settings) -> AuthMode:
    """The mode this process serves. An unknown value follows the environment default."""
    raw = str(settings.auth_mode or "").strip().lower()
    if raw == AuthMode.PASSWORD.value:
        return AuthMode.PASSWORD
    if raw == AuthMode.OIDC.value:
        return AuthMode.OIDC
    if settings.env in {EnvName.DEV, EnvName.CI}:
        return AuthMode.PASSWORD
    return AuthMode.OIDC


def password_mode_allowed(settings: Settings) -> bool:
    """Password sign-in is dev, CI, or an explicit single-tenant opt-in."""
    if settings.env in {EnvName.DEV, EnvName.CI}:
        return True
    return settings.deployment_mode is DeploymentMode.SINGLE_TENANT and bool(
        settings.password_login
    )


def assert_auth_mode(settings: Settings) -> None:
    """Refuse a production boot that would serve the weaker mode, or OIDC with no issuer."""
    mode = resolve_auth_mode(settings)
    if mode is AuthMode.PASSWORD and not password_mode_allowed(settings):
        raise RuntimeError(
            "AR_AUTH_MODE=password is only for dev, ci, or a single-tenant install "
            "with AR_PASSWORD_LOGIN=true. It is not the production default."
        )
    if mode is AuthMode.OIDC and settings.env not in {EnvName.DEV, EnvName.CI}:
        issuer = settings.oidc_issuer.strip()
        client_id = settings.oidc_client_id.strip()
        if not issuer or not client_id:
            raise RuntimeError(
                "AR_OIDC_ISSUER and AR_OIDC_CLIENT_ID are required when auth mode is oidc"
            )


def cookies_are_secure(settings: Settings) -> bool:
    """Session cookies are Secure outside dev and CI. Local HTTP stays usable."""
    return settings.env not in {EnvName.DEV, EnvName.CI}
