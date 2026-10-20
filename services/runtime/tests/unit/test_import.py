"""Trivial import test for ar_runtime."""

import ar_runtime


def test_ar_runtime_imports() -> None:
    assert ar_runtime.__version__ == "0.1.0"
