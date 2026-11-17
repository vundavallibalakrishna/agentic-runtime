"""Create and check application database roles. SQLAlchemy stays in this module.

``ar_common.database_roles`` holds the password rules so the web app can refuse
a bad URL without pulling a database driver into channels and the sandbox agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from ar_common.database_roles import APPLICATION_ROLES, ROLE_ATTRIBUTES, role_password

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

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


def apply_database_roles(connection: Connection) -> None:
    """Create or check the four roles and set their passwords from the environment.

    A superuser session writes the attributes. A later session as ``ar_owner``
    cannot grant ``BYPASSRLS``, so it only checks the attributes and sets the
    passwords. PostgreSQL also requires ``ADMIN OPTION`` for that password change.
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
