"""Application database roles and their passwords.

One contract for compose, Helm and migrations. A password is an environment
variable supplied at install time. Nothing in this module invents one, and a
missing, placeholder or role-name password is refused in every environment.

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
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.engine import make_url

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

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

_EXPECTED_FLAGS: dict[str, dict[str, bool]] = {
    "ar_owner": {
        "rolsuper": False,
        "rolcreatedb": True,
        "rolcreaterole": True,
        "rolbypassrls": True,
        "rolcanlogin": True,
    },
    "ar_platform": {
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolbypassrls": True,
        "rolcanlogin": True,
    },
    "ar_app": {
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolbypassrls": False,
        "rolcanlogin": True,
    },
    "ar_readonly": {
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolbypassrls": False,
        "rolcanlogin": True,
    },
}


def reject_database_password(role: str, password: str) -> None:
    """Raise when ``password`` is empty, a known placeholder, or the role name."""
    folded = password.strip().casefold()
    env_name = PASSWORD_ENV.get(role, role)
    if folded in PLACEHOLDERS or folded == role.strip().casefold():
        message = f"{env_name} is unset, a placeholder, or the role name"
        raise RuntimeError(message)


def role_password(role: str) -> str:
    """The install-time password for ``role``. Never a generated or fixed fallback."""
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
    parsed = make_url(url)
    user = parsed.username or ""
    if user not in PASSWORD_ENV:
        return
    reject_database_password(user, parsed.password or "")


def apply_database_roles(connection: Connection) -> None:
    """Create or check the four roles and set their passwords from the environment.

    A superuser session (image init, then the first migration) writes the
    attributes. A later session as ``ar_owner`` cannot grant ``BYPASSRLS``, so it
    only checks the attributes and sets the passwords.
    """
    superuser = connection.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if superuser:
        for role in APPLICATION_ROLES:
            _create_or_alter(connection, role)
        _grant_admin(connection)
        return
    _require_attributes(connection)
    for role in APPLICATION_ROLES:
        _set_password(connection, role)


def _grant_admin(connection: Connection) -> None:
    """Let ar_owner apply a later password from the environment.

    PostgreSQL requires ADMIN OPTION on the other role, not only CREATEROLE.
    """
    for role in ("ar_app", "ar_platform", "ar_readonly"):
        connection.execute(text(f"GRANT {role} TO ar_owner WITH ADMIN OPTION"))


def _create_or_alter(connection: Connection, role: str) -> None:
    password = role_password(role)
    attributes = ROLE_ATTRIBUTES[role]
    exists = connection.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
        {"role": role},
    ).scalar()
    verb = "ALTER ROLE" if exists else "CREATE ROLE"
    statement = connection.execute(
        text(
            "SELECT format("
            f"'{verb} %I WITH {attributes} PASSWORD %L', "
            "CAST(:role AS text), CAST(:password AS text))"
        ),
        {"role": role, "password": password},
    ).scalar()
    if not isinstance(statement, str) or not statement.startswith(verb):
        message = f"could not build the role statement for {role}"
        raise RuntimeError(message)
    connection.execute(text(statement))


def _set_password(connection: Connection, role: str) -> None:
    password = role_password(role)
    statement = connection.execute(
        text(
            "SELECT format('ALTER ROLE %I PASSWORD %L', "
            "CAST(:role AS text), CAST(:password AS text))"
        ),
        {"role": role, "password": password},
    ).scalar()
    if not isinstance(statement, str) or "PASSWORD" not in statement:
        message = f"could not build the password statement for {role}"
        raise RuntimeError(message)
    connection.execute(text(statement))


def _require_attributes(connection: Connection) -> None:
    for role, expected in _EXPECTED_FLAGS.items():
        row = (
            connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolcanlogin "
                    "FROM pg_roles WHERE rolname = :role"
                ),
                {"role": role},
            )
            .mappings()
            .first()
        )
        if row is None:
            message = f"{role} is missing. The database superuser must create it before migrate."
            raise RuntimeError(message)
        for flag, want in expected.items():
            if bool(row[flag]) is not want:
                message = f"{role} has {flag}={row[flag]!s}; expected {want}"
                raise RuntimeError(message)
