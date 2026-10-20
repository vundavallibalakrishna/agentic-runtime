"""Trivial import test for ar_ingest."""

import ar_ingest


def test_ar_ingest_imports() -> None:
    assert ar_ingest.__version__ == "0.1.0"
