"""Schema gate and Temporal database names. No live database and no secrets in the output."""

from __future__ import annotations

import pytest

from ar_domain.db.role_admin import temporal_database_names
from ar_domain.db.schema_gate import _redact, head_revision


def test_head_revision_is_one_value() -> None:
    assert head_revision()


def test_redact_removes_role_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_DB_TEMPORAL_PASSWORD", "temporal-secret-value")
    monkeypatch.setenv("POSTGRES_PASSWORD", "super-secret-value")
    text = _redact("failed temporal-secret-value and super-secret-value")
    assert "temporal-secret-value" not in text
    assert "super-secret-value" not in text
    assert "[redacted]" in text


def test_temporal_database_names_reject_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPORAL_DBNAME", "temporal;drop")
    with pytest.raises(RuntimeError, match="lowercase identifier"):
        temporal_database_names()


def test_schema_gate_refuses_a_missing_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AR_DATABASE_URL", "")
    from ar_domain.db.schema_gate import main

    with pytest.raises(SystemExit):
        main()
    error = capsys.readouterr().err
    assert "AR_DATABASE_URL is unset" in error
    assert "secret" not in error
