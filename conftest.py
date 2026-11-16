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


def pytest_configure() -> None:
    """Unresolvable test hostnames fall back to TEST-NET so mocks still match.

    A test that replaces ``resolve_host`` sees its own function. A test that
    must observe a real lookup failure sets ``AR_EGRESS_STRICT_DNS=1``.
    """
    from ar_common import egress_http  # noqa: PLC0415

    original = egress_http.resolve_host

    def fallback(host: str) -> list[str]:
        try:
            return original(host)
        except egress_http.EgressDenied:
            if os.environ.get("AR_EGRESS_STRICT_DNS") == "1":
                raise
            return ["8.8.8.8"]

    egress_http.resolve_host = fallback


def pytest_addoption(parser: object) -> None:
    """Register ``--with-qdrant`` for the optional retrieval adapter."""
    parser.addoption("--with-qdrant", action="store_true", default=False)  # type: ignore[attr-defined]
