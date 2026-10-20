"""Compose smoke retries until each health URL responds."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("compose_smoke", ROOT / "scripts" / "smoke.py")
assert _SPEC is not None
assert _SPEC.loader is not None
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)


def test_smoke_retries_until_healthy(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    attempts = {"n": 0}

    def fake_get(url: str) -> tuple[bool, str]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("connection refused")
        return True, '{"status":"ok"}'

    monkeypatch.setattr(smoke, "_get", fake_get)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke.py",
            "--health-only",
            "--url",
            "http://localhost:9/healthz",
            "--wait-seconds",
            "2",
            "--interval-seconds",
            "0.01",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        smoke.main()
    assert exc.value.code == 0
    assert attempts["n"] == 2
    output = capsys.readouterr().out
    assert "ok http://localhost:9/healthz" in output
    assert "FAIL" not in output


def test_smoke_fails_when_health_never_arrives(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_get(url: str) -> tuple[bool, str]:
        raise OSError("connection refused")

    monkeypatch.setattr(smoke, "_get", fake_get)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke.py",
            "--health-only",
            "--url",
            "http://localhost:9/healthz",
            "--wait-seconds",
            "0",
            "--interval-seconds",
            "0.01",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        smoke.main()
    assert exc.value.code == 1
    assert "FAIL http://localhost:9/healthz" in capsys.readouterr().out


def test_smoke_rejects_non_http_without_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str) -> tuple[bool, str]:
        raise AssertionError(url)

    monkeypatch.setattr(smoke, "_get", fake_get)
    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke.py", "--health-only", "--url", "file:///etc/passwd", "--wait-seconds", "5"],
    )
    with pytest.raises(SystemExit) as exc:
        smoke.main()
    assert exc.value.code == 1
