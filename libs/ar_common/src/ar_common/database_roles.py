"""Application database role passwords.

One contract for Compose and migrations. A password is an environment
variable supplied at install time. Dev and CI generate values with
``generated_password``; nothing falls back to the role name or a placeholder.

``ar_owner`` is the migration, bootstrap and seed login. ``plans`` has
``FORCE ROW LEVEL SECURITY`` and only a ``SELECT`` policy, and system ``roles``
are inserted with ``tenant_id`` NULL, so that login cannot write the catalogue
unless it bypasses row security. It is not a superuser and it cannot create
databases or roles. The image superuser creates ``temporal`` and ``langfuse``
and reconciles an existing volume before Alembic runs.

``ar_platform`` bypasses row security because ``platform_session`` runs before a
tenant is known. ``ar_app``, ``ar_readonly`` and ``ar_temporal`` do not.
``ar_temporal`` owns the Temporal databases only. It is not a tenant login and
it does not bypass row security.
"""

from __future__ import annotations

import os
import secrets
from urllib.parse import quote, unquote, urlsplit, urlunsplit

APPLICATION_ROLES: tuple[str, ...] = (
    "ar_owner",
    "ar_app",
    "ar_platform",
    "ar_readonly",
    "ar_temporal",
)

PASSWORD_ENV: dict[str, str] = {
    "ar_owner": "AR_DB_OWNER_PASSWORD",
    "ar_app": "AR_DB_APP_PASSWORD",
    "ar_platform": "AR_DB_PLATFORM_PASSWORD",
    "ar_readonly": "AR_DB_READONLY_PASSWORD",
    "ar_temporal": "AR_DB_TEMPORAL_PASSWORD",
}

TEMPORAL_DATABASE: str = "temporal"
TEMPORAL_VISIBILITY_DATABASE: str = "temporal_visibility"

# Compared case-insensitively. Role names are included so ``Ar_Owner`` is refused.
PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "",
        "ar-install-db",
        "airgap-set-a-real-password",
        "changeme",
        "change-me",
        "password",
        "placeholder",
        "postgres",
        "install-time",
        "ar_owner",
        "ar_app",
        "ar_platform",
        "ar_readonly",
        "ar_temporal",
    }
)

# Attributes a superuser must leave on the role. Bootstrap and migrate both read these.
ROLE_ATTRIBUTES: dict[str, str] = {
    "ar_owner": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS",
    "ar_platform": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS",
    "ar_app": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS",
    "ar_readonly": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS",
    "ar_temporal": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS",
}


def generated_password() -> str:
    """A URL-safe password for dev and CI. The same function fills every path."""
    return secrets.token_urlsafe(24)


def reject_database_password(role: str, password: str) -> None:
    """Raise when ``password`` is empty, a known placeholder, or the role name."""
    folded = password.strip().casefold()
    env_name = PASSWORD_ENV.get(role, role)
    if folded in PLACEHOLDERS or folded == role.strip().casefold():
        message = f"{env_name} is unset, a placeholder, or the role name"
        raise RuntimeError(message)


def role_password(role: str) -> str:
    """The install-time password for ``role``. Never a fixed fallback."""
    if role not in PASSWORD_ENV:
        message = f"{role} is not an application database role"
        raise RuntimeError(message)
    raw = os.environ.get(PASSWORD_ENV[role], "")
    reject_database_password(role, raw)
    return raw.strip()


def refuse_set_password(password: str | None) -> None:
    """Refuse an empty, placeholder, or role-name password.

    ``None`` is a passwordless URL, which dev fixtures use. An empty string is
    a password that was set to nothing, and staging and production refuse it.
    """
    if password is None:
        return
    if password == "":
        message = "database URL password is unset, a placeholder, or a role name"
        raise RuntimeError(message)
    folded = unquote(password).strip().casefold()
    if folded in PLACEHOLDERS or folded in {role.casefold() for role in APPLICATION_ROLES}:
        message = "database URL password is unset, a placeholder, or a role name"
        raise RuntimeError(message)


def assert_application_url(url: str) -> None:
    """Refuse an application-role URL whose password is a placeholder or the role name."""
    if not url or "://" not in url:
        return
    parts = urlsplit(url)
    user = unquote(parts.username or "")
    if user not in PASSWORD_ENV:
        return
    reject_database_password(user, unquote(parts.password or ""))


def assert_installed_database_secrets(env: str, database_url: str) -> None:
    """Staging and production require real role passwords and real database URLs.

    Dev and CI return without checking. Every other environment checks the
    ``AR_DB_*_PASSWORD`` values, the given URL, and the owner and platform URLs
    derived from it. Compose staging and production get this check at process
    start.
    """
    if str(env).strip().casefold() in {"dev", "ci"}:
        return
    for role in APPLICATION_ROLES:
        role_password(role)
    _assert_any_url(database_url)
    parts = urlsplit(database_url)
    user = unquote(parts.username or "")
    if user in {"ar_app", "ar_owner", "ar_platform", "ar_readonly"}:
        for role in ("ar_owner", "ar_platform"):
            _assert_any_url(_swap_url(database_url, role, role_password(role)))


def _assert_any_url(url: str) -> None:
    if not url or "://" not in url:
        message = "database URL is unset"
        raise RuntimeError(message)
    parts = urlsplit(url)
    user = unquote(parts.username or "")
    password = unquote(parts.password or "")
    if user in PASSWORD_ENV:
        reject_database_password(user, password)
        return
    folded = password.strip().casefold()
    if folded in PLACEHOLDERS or folded in {role.casefold() for role in APPLICATION_ROLES}:
        message = "database URL password is unset, a placeholder, or a role name"
        raise RuntimeError(message)


def _swap_url(url: str, username: str, password: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
