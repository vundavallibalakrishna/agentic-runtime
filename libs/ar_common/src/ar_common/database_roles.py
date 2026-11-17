"""Application database role passwords.

One contract for compose, Helm and migrations. A password is an environment
variable supplied at install time. Dev and CI generate values with
``generated_password``; nothing falls back to the role name or a placeholder.

``ar_owner`` is the migration, bootstrap and seed login. ``plans`` has
``FORCE ROW LEVEL SECURITY`` and only a ``SELECT`` policy, and system ``roles``
are inserted with ``tenant_id`` NULL, so that login cannot write the catalogue
unless it bypasses row security. It is not a superuser. ``CREATEDB`` is how the
CloudNativePG owner creates ``temporal`` and ``langfuse``. ``CREATEROLE`` is how
the first revision creates the other logins when it is connected as a superuser.

``ar_platform`` bypasses row security because ``platform_session`` runs before a
tenant is known. ``ar_app`` and ``ar_readonly`` do not.
"""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

if TYPE_CHECKING:
    from pathlib import Path

APPLICATION_ROLES: tuple[str, ...] = ("ar_owner", "ar_app", "ar_platform", "ar_readonly")

PASSWORD_ENV: dict[str, str] = {
    "ar_owner": "AR_DB_OWNER_PASSWORD",
    "ar_app": "AR_DB_APP_PASSWORD",
    "ar_platform": "AR_DB_PLATFORM_PASSWORD",
    "ar_readonly": "AR_DB_READONLY_PASSWORD",
}

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
    }
)

# Attributes a superuser must leave on the role. Bootstrap and migrate both read these.
ROLE_ATTRIBUTES: dict[str, str] = {
    "ar_owner": "LOGIN NOSUPERUSER CREATEDB CREATEROLE BYPASSRLS",
    "ar_platform": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS",
    "ar_app": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS",
    "ar_readonly": "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS",
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


def assert_application_url(url: str) -> None:
    """Refuse an application-role URL whose password is a placeholder or the role name."""
    if not url or "://" not in url:
        return
    parts = urlsplit(url)
    user = unquote(parts.username or "")
    if user not in PASSWORD_ENV:
        return
    reject_database_password(user, unquote(parts.password or ""))


def write_helm_passwords(path: Path) -> None:
    """Write a Helm values overlay. The file is generated per run and not committed."""
    lines = ["secrets:", "  data:"]
    lines.extend(f"    {key}: {generated_password()}" for key in PASSWORD_ENV.values())
    lines.append("postgres:")
    lines.append(f"  superuserPassword: {generated_password()}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
