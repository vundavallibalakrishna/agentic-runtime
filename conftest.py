"""Root pytest plugins."""

import os

# Tests run model servers, tool servers and web pages on this machine's own addresses.
# Reaching them is a setting of the install (``AR_EGRESS_ALLOW_LOOPBACK``), off by default,
# so the test run turns it on here, before any settings are read.
os.environ.setdefault("AR_EGRESS_ALLOW_LOOPBACK", "true")
os.environ.setdefault("AR_EGRESS_ALLOW_WILDCARD", "true")
os.environ.setdefault("AR_SANDBOX_ALLOW_UNISOLATED", "true")
os.environ.setdefault("AR_FILES_SCANNER", "none")

pytest_plugins = [
    "ar_testing.containers",
    "ar_testing.temporal",
    "ar_testing.fake_llm",
    "ar_testing.stand_in",
    "ar_testing.auth",
]


def pytest_addoption(parser: object) -> None:
    """Register ``--with-qdrant`` for the optional retrieval adapter."""
    parser.addoption("--with-qdrant", action="store_true", default=False)  # type: ignore[attr-defined]
