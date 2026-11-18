"""libpq dials the pinned address and still runs a statement."""

from __future__ import annotations

import os

import psycopg
import pytest

from ar_domain.tools.database import _dial

pytestmark = pytest.mark.integration


def test_hostaddr_reaches_postgres(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_DATABASE_URL", raising=False)
    os.environ.pop("AR_DATABASE_URL", None)
    dial = _dial(postgres_url, {"allow_platform": True}, [])
    assert "hostaddr=" in dial.dsn
    with psycopg.connect(dial.dsn, connect_timeout=5) as conn:
        row = conn.execute("SELECT 1").fetchone()
    assert row is not None
    assert row[0] == 1
