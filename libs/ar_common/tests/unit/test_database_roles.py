"""Role passwords are install-time values, never the role name."""

from pathlib import Path

import pytest

from ar_common.database_roles import (
    APPLICATION_ROLES,
    PLACEHOLDERS,
    ROLE_ATTRIBUTES,
    assert_application_url,
    assert_installed_database_secrets,
    refuse_set_password,
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
    assert "NOBYPASSRLS" in ROLE_ATTRIBUTES["ar_temporal"]
    owner = set(ROLE_ATTRIBUTES["ar_owner"].split())
    assert "NOCREATEDB" in owner
    assert "NOCREATEROLE" in owner
    assert "CREATEDB" not in owner
    assert "CREATEROLE" not in owner


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
                "rolcreatedb": False,
                "rolcreaterole": False,
                "rolbypassrls": role in {"ar_owner", "ar_platform"},
                "rolcanlogin": True,
            }
            for role in APPLICATION_ROLES
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
    from ar_domain.db.role_admin import apply_database_roles

    apply_database_roles(connection)  # type: ignore[arg-type]
    assert not any("GRANT" in item for item in connection.statements)
    assert any(item.startswith("CREATE ROLE ar_owner") for item in connection.statements)


def test_owner_session_checks_attributes_and_does_not_set_passwords(
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
    from ar_domain.db.role_admin import apply_database_roles

    apply_database_roles(connection)  # type: ignore[arg-type]
    assert not any("PASSWORD" in item for item in connection.statements)


def test_owner_session_refuses_a_missing_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_DB_OWNER_PASSWORD", "owner-secret")
    connection = _Connection(superuser=False)
    from ar_domain.db.role_admin import apply_database_roles

    with pytest.raises(RuntimeError, match="ar_owner is missing"):
        apply_database_roles(connection)  # type: ignore[arg-type]


def test_installed_secrets_refuse_placeholders_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_DB_OWNER_PASSWORD", "owner-secret")
    monkeypatch.setenv("AR_DB_APP_PASSWORD", "app-secret")
    monkeypatch.setenv("AR_DB_PLATFORM_PASSWORD", "platform-secret")
    monkeypatch.setenv("AR_DB_READONLY_PASSWORD", "readonly-secret")
    url = "postgresql+asyncpg://ar_app:app-secret@localhost/ar"
    assert_installed_database_secrets("dev", url)
    assert_installed_database_secrets("ci", "postgresql://postgres:ar_owner@localhost/ar")
    assert_installed_database_secrets("staging", url)
    monkeypatch.setenv("AR_DB_APP_PASSWORD", "ar_app")
    with pytest.raises(RuntimeError, match="AR_DB_APP_PASSWORD"):
        assert_installed_database_secrets("prod", url)
    monkeypatch.setenv("AR_DB_APP_PASSWORD", "app-secret")
    with pytest.raises(RuntimeError, match="database URL password"):
        assert_installed_database_secrets(
            "staging", "postgresql://postgres:ar_owner@localhost/agentic_runtime"
        )


def test_refuse_set_password_allows_a_passwordless_url() -> None:
    refuse_set_password(None)
    with pytest.raises(RuntimeError):
        refuse_set_password("")
    with pytest.raises(RuntimeError):
        refuse_set_password("ar_owner")


def test_reconcile_skips_only_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.db.reconcile_roles import main

    monkeypatch.setenv("AR_DB_RECONCILE", "cnpg")
    main()
    monkeypatch.setenv("AR_DB_RECONCILE", "skip")
    main()
    monkeypatch.setenv("AR_DB_RECONCILE", "external")
    main()
    monkeypatch.setenv("AR_DB_RECONCILE", "run")
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql+asyncpg://ar_app:app-secret@db.internal/ar")
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("AR_DB_SUPERUSER_URL", raising=False)
    with pytest.raises(SystemExit):
        main()


def test_reconcile_login_redacts_and_does_not_connect(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ar_domain.db.reconcile_roles import _engine, _login, _redact, _target_configured, main

    monkeypatch.setenv("AR_DB_RECONCILE", "nope")
    with pytest.raises(SystemExit):
        main()
    assert "must be run" in capsys.readouterr().err

    monkeypatch.delenv("AR_DB_SUPERUSER_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "image-secret")
    monkeypatch.setenv("POSTGRES_PORT", "")
    monkeypatch.setenv("POSTGRES_DB", "")
    monkeypatch.setenv("AR_PG_HOST_PORT", "55439")
    login = _login()
    assert login["user"] == "postgres"
    assert login["port"] == 55439
    assert login["database"] == "agentic_runtime"
    assert _redact(f"failed {login['password']}") == "failed [redacted]"
    assert _redact("") == ""
    engine = _engine()
    engine.dispose()

    monkeypatch.setenv(
        "AR_DB_SUPERUSER_URL",
        "postgresql://ar_app:old-secret@db.example:5433/agentic_runtime",
    )
    explicit = _login()
    assert explicit["host"] == "db.example"
    assert explicit["port"] == 5433
    assert explicit["user"] == "ar_app"
    monkeypatch.setenv("AR_DB_SUPERUSER_URL", "postgresql://db.example/agentic_runtime")
    with pytest.raises(RuntimeError, match="username and password"):
        _login()

    monkeypatch.delenv("AR_DB_SUPERUSER_URL")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
        _login()

    monkeypatch.setenv("AR_DB_RECONCILE", "run")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PASSWORD", "image-secret")
    for name in (
        "AR_DB_OWNER_PASSWORD",
        "AR_DB_APP_PASSWORD",
        "AR_DB_PLATFORM_PASSWORD",
        "AR_DB_READONLY_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    assert _target_configured() is True
    with pytest.raises(SystemExit):
        main()
    error = capsys.readouterr().err
    assert "role reconciliation failed" in error
    assert "image-secret" not in error

    monkeypatch.delenv("POSTGRES_HOST")
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql://ar_app:app-secret@localhost/ar")
    assert _target_configured() is True


def test_placeholder_copies_match() -> None:
    """Helm and the init script refuse the same values as PLACEHOLDERS."""
    root = Path(__file__).resolve().parents[4]
    shell = (root / "deploy/helm/agentic-runtime/files/init-roles.sh").read_text(encoding="utf-8")
    case = shell.split("case $folded in", 1)[1].split(")", 1)[0]
    shell_tokens = {item.strip() for item in case.split("|") if item.strip()}
    helm = (root / "deploy/helm/agentic-runtime/templates/_helpers.tpl").read_text(encoding="utf-8")
    listed = helm.split("$bad := list ", 1)[1].split(" -}}", 1)[0]
    helm_tokens = {item.strip().strip('"') for item in listed.split() if item.startswith('"')}
    assert shell_tokens == PLACEHOLDERS - {""}
    assert helm_tokens == PLACEHOLDERS


def test_create_app_refuses_a_staging_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from ar_common.web.app import _refuse_database_password

    monkeypatch.setenv("AR_DB_OWNER_PASSWORD", "owner-secret")
    monkeypatch.setenv("AR_DB_APP_PASSWORD", "ar_app")
    monkeypatch.setenv("AR_DB_PLATFORM_PASSWORD", "platform-secret")
    monkeypatch.setenv("AR_DB_READONLY_PASSWORD", "readonly-secret")
    settings = SimpleNamespace(
        env="staging", database_url="postgresql://ar_app:ar_app@localhost/ar"
    )
    with pytest.raises(RuntimeError, match="AR_DB_APP_PASSWORD"):
        _refuse_database_password(settings)  # type: ignore[arg-type]


def test_migration_entrypoint_refuses_a_staging_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.db.installed_secrets import check_migration_secrets

    monkeypatch.setenv("AR_ENV", "staging")
    monkeypatch.setenv("AR_DB_OWNER_PASSWORD", "owner-secret")
    monkeypatch.setenv("AR_DB_APP_PASSWORD", "app-secret")
    monkeypatch.setenv("AR_DB_PLATFORM_PASSWORD", "platform-secret")
    monkeypatch.setenv("AR_DB_READONLY_PASSWORD", "readonly-secret")
    with pytest.raises(RuntimeError, match="database URL password"):
        check_migration_secrets("postgresql+asyncpg://postgres:ar_owner@localhost/ar")


def test_bootstrap_entrypoint_refuses_a_staging_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain import bootstrap as bootstrap_module

    monkeypatch.setenv("AR_ENV", "prod")
    monkeypatch.setenv("AR_DB_OWNER_PASSWORD", "ar_owner")
    monkeypatch.setenv("AR_DB_APP_PASSWORD", "app-secret")
    monkeypatch.setenv("AR_DB_PLATFORM_PASSWORD", "platform-secret")
    monkeypatch.setenv("AR_DB_READONLY_PASSWORD", "readonly-secret")
    monkeypatch.setattr(
        bootstrap_module,
        "app_database_url",
        lambda: "postgresql+asyncpg://ar_app:app-secret@localhost/ar",
    )
    with pytest.raises(RuntimeError, match="AR_DB_OWNER_PASSWORD"):
        bootstrap_module.check_bootstrap_secrets()
