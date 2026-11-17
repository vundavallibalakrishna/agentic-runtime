"""Role passwords are install-time values, never the role name."""

import pytest

from ar_common.database_roles import (
    ROLE_ATTRIBUTES,
    assert_application_url,
    reject_database_password,
    role_password,
)


def test_attributes_are_not_superuser() -> None:
    for attributes in ROLE_ATTRIBUTES.values():
        assert attributes.split()[0] == "LOGIN"
        assert "NOSUPERUSER" in attributes.split()
        assert "SUPERUSER" not in attributes.split()
    assert "BYPASSRLS" in ROLE_ATTRIBUTES["ar_owner"]
    assert "NOBYPASSRLS" not in ROLE_ATTRIBUTES["ar_owner"]
    assert "BYPASSRLS" in ROLE_ATTRIBUTES["ar_platform"]
    assert "NOBYPASSRLS" in ROLE_ATTRIBUTES["ar_app"]
    assert "NOBYPASSRLS" in ROLE_ATTRIBUTES["ar_readonly"]
    assert "CREATEDB" in ROLE_ATTRIBUTES["ar_owner"]
    assert "CREATEROLE" in ROLE_ATTRIBUTES["ar_owner"]


def test_password_rejects_placeholders_and_role_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_DB_OWNER_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="AR_DB_OWNER_PASSWORD"):
        role_password("ar_owner")
    for bad in ("ar_owner", "Ar_Owner", "CHANGEME", "install-time", "ar-install-db"):
        with pytest.raises(RuntimeError):
            reject_database_password("ar_owner", bad)
    reject_database_password("ar_owner", "a-real-secret")


def test_role_password_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_DB_PLATFORM_PASSWORD", "platform-secret")
    assert role_password("ar_platform") == "platform-secret"


def test_application_url_refuses_a_role_name_password() -> None:
    with pytest.raises(RuntimeError):
        assert_application_url("postgresql+asyncpg://ar_app:ar_app@localhost/ar")
    assert_application_url("postgresql+asyncpg://ar_app:a-real-secret@localhost/ar")
    assert_application_url("postgresql://postgres:ci-image-superuser@localhost/ar")


class _Result:
    def __init__(self, value: object = None, row: dict[str, object] | None = None) -> None:
        self._value = value
        self._row = row

    def scalar(self) -> object:
        return self._value

    def mappings(self) -> _Result:
        return self

    def first(self) -> dict[str, object] | None:
        return self._row


class _Connection:
    def __init__(self, *, superuser: bool, exists: bool = False) -> None:
        self.superuser = superuser
        self.exists = exists
        self.flags = {
            role: {
                "rolsuper": False,
                "rolcreatedb": role == "ar_owner",
                "rolcreaterole": role == "ar_owner",
                "rolbypassrls": role in {"ar_owner", "ar_platform"},
                "rolcanlogin": True,
            }
            for role in ("ar_owner", "ar_app", "ar_platform", "ar_readonly")
        }
        self.statements: list[str] = []

    def execute(self, clause: object, params: dict[str, str] | None = None) -> _Result:
        sql = str(clause)
        self.statements.append(sql)
        if "current_user" in sql:
            return _Result(self.superuser)
        if "SELECT 1 FROM pg_roles" in sql:
            return _Result(1 if self.exists else None)
        if "rolbypassrls" in sql:
            if not self.exists:
                return _Result(row=None)
            role = (params or {})["role"]
            return _Result(row=self.flags.get(role))
        if "SELECT format" in sql:
            role = (params or {})["role"]
            password = (params or {})["password"]
            verb = "ALTER ROLE" if "ALTER ROLE" in sql and self.exists else "CREATE ROLE"
            if "WITH" in sql:
                return _Result(f"{verb} {role} WITH LOGIN PASSWORD '{password}'")
            return _Result(f"ALTER ROLE {role} PASSWORD '{password}'")
        return _Result()


def test_superuser_session_creates_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "AR_DB_OWNER_PASSWORD": "owner-secret",
        "AR_DB_APP_PASSWORD": "app-secret",
        "AR_DB_PLATFORM_PASSWORD": "platform-secret",
        "AR_DB_READONLY_PASSWORD": "readonly-secret",
    }.items():
        monkeypatch.setenv(key, value)
    connection = _Connection(superuser=True)
    from ar_common.database_roles import apply_database_roles

    apply_database_roles(connection)  # type: ignore[arg-type]
    assert any(
        "GRANT ar_app TO ar_owner WITH ADMIN OPTION" in item for item in connection.statements
    )
    assert any(item.startswith("CREATE ROLE ar_owner") for item in connection.statements)


def test_owner_session_checks_attributes_and_sets_passwords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in {
        "AR_DB_OWNER_PASSWORD": "owner-secret",
        "AR_DB_APP_PASSWORD": "app-secret",
        "AR_DB_PLATFORM_PASSWORD": "platform-secret",
        "AR_DB_READONLY_PASSWORD": "readonly-secret",
    }.items():
        monkeypatch.setenv(key, value)
    connection = _Connection(superuser=False, exists=True)
    from ar_common.database_roles import apply_database_roles

    apply_database_roles(connection)  # type: ignore[arg-type]
    assert any(item.startswith("ALTER ROLE ar_app PASSWORD") for item in connection.statements)


def test_owner_session_refuses_a_missing_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_DB_OWNER_PASSWORD", "owner-secret")
    connection = _Connection(superuser=False)
    from ar_common.database_roles import apply_database_roles

    with pytest.raises(RuntimeError, match="ar_owner is missing"):
        apply_database_roles(connection)  # type: ignore[arg-type]
