"""Schema gate and Temporal database names. No live database and no secrets in the output."""

from __future__ import annotations

import pytest

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


def test_a_failed_upgrade_shows_the_end_of_its_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from types import SimpleNamespace

    from ar_domain.db import schema_gate

    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret-value")
    output = (
        "Traceback (most recent call last):\n"
        + "  frame\n" * 400
        + "KeyError: 'the cause' for s3cret-value\n"
    )
    monkeypatch.setattr(
        schema_gate.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr=output, stdout=""),
    )
    with pytest.raises(SystemExit):
        schema_gate._run_alembic()
    shown = capsys.readouterr().err
    assert "KeyError: 'the cause' for [redacted]" in shown
    assert "s3cret-value" not in shown
    assert len(shown) < 2100
