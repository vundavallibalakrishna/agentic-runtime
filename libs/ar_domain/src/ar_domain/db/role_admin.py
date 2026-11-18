"""Create and check application database roles. SQLAlchemy stays in this module.

``ar_common.database_roles`` holds the password rules so the web app can refuse
a bad URL without pulling a database driver into channels and the sandbox agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from ar_common.database_roles import (
    APPLICATION_ROLES,
    ROLE_ATTRIBUTES,
    TEMPORAL_DATABASE,
    TEMPORAL_VISIBILITY_DATABASE,
    role_password,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

_EXPECTED_FLAGS: dict[str, dict[str, bool]] = {
    "ar_owner": {
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
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
    "ar_temporal": {
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolbypassrls": False,
        "rolcanlogin": True,
    },
}


def apply_database_roles(connection: Connection, *, require_superuser: bool = False) -> None:
    """Create or check the application roles and set their passwords from the environment.

    A superuser session writes the attributes and the passwords. ``ar_owner`` has
    no ``CREATEROLE``, so a later session only checks the attributes. The upgrade
    command passes ``require_superuser`` so a non-superuser login cannot look like
    a successful reconciliation of an old ``SUPERUSER`` role.
    """
    superuser = connection.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if require_superuser and not superuser:
        message = "role reconciliation requires the database superuser"
        raise RuntimeError(message)
    if superuser:
        # Altering the session role to NOSUPERUSER first would make the rest fail.
        current = connection.execute(text("SELECT current_user")).scalar()
        ordered = [role for role in APPLICATION_ROLES if role != current]
        if current in APPLICATION_ROLES:
            ordered.append(str(current))
        for role in ordered:
            _create_or_alter(connection, role)
        return
    _require_attributes(connection)


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


def ensure_temporal_databases(connection: Connection) -> None:
    """Create ``ar_temporal`` and its two databases. The caller uses autocommit.

    ``CREATE DATABASE`` cannot run inside a transaction.
    """
    _create_or_alter(connection, "ar_temporal")
    for name in (TEMPORAL_DATABASE, TEMPORAL_VISIBILITY_DATABASE):
        _ensure_database(connection, name)


def _ensure_database(connection: Connection, name: str) -> None:
    if not name.isidentifier():
        message = "temporal database name is not an identifier"
        raise RuntimeError(message)
    exists = connection.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :name"),
        {"name": name},
    ).scalar()
    if not exists:
        connection.execute(text(f"CREATE DATABASE {name} OWNER ar_temporal"))
    connection.execute(text(f"ALTER DATABASE {name} OWNER TO ar_temporal"))
    connection.execute(text(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC"))
    connection.execute(text(f"GRANT ALL ON DATABASE {name} TO ar_temporal"))
