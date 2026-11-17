"""Root pytest plugins."""

import os

# Tests run model servers, tool servers and web pages on this machine's own addresses.
# Reaching them is a setting of the install (``AR_EGRESS_ALLOW_LOOPBACK``), off by default,
# so the test run turns it on here, before any settings are read.
os.environ.setdefault("AR_EGRESS_ALLOW_LOOPBACK", "true")
os.environ.setdefault("AR_EGRESS_ALLOW_WILDCARD", "true")
os.environ.setdefault("AR_SANDBOX_ALLOW_UNISOLATED", "true")
os.environ.setdefault("AR_FILES_SCANNER", "none")
os.environ.setdefault("AR_DB_OWNER_PASSWORD", "test-owner-password")
os.environ.setdefault("AR_DB_PLATFORM_PASSWORD", "test-platform-password")
os.environ.setdefault("AR_DB_APP_PASSWORD", "test-app-password")
os.environ.setdefault("AR_DB_READONLY_PASSWORD", "test-readonly-password")

pytest_plugins = [
    "ar_testing.containers",
    "ar_testing.temporal",
    "ar_testing.fake_llm",
    "ar_testing.stand_in",
    "ar_testing.auth",
]


def pytest_configure(config: object) -> None:
    """Register the opt-in marker. Unresolved names fail unless a test asks."""
    config.addinivalue_line(  # type: ignore[attr-defined]
        "markers",
        "dns_fallback: an unresolved name is treated as 8.8.8.8 so a mock can match",
    )


_DNS_ORIGINAL: object = None


def pytest_runtest_setup(item: object) -> None:
    """Install the fallback only for tests marked ``dns_fallback``."""
    global _DNS_ORIGINAL  # noqa: PLW0603
    marker = getattr(item, "get_closest_marker", lambda _name: None)("dns_fallback")
    if marker is None:
        return
    from ar_common import egress_http  # noqa: PLC0415

    _DNS_ORIGINAL = egress_http.resolve_host

    def fallback(host: str) -> list[str]:
        try:
            return _DNS_ORIGINAL(host)  # type: ignore[operator]
        except egress_http.EgressDenied:
            return ["8.8.8.8"]

    egress_http.resolve_host = fallback


def pytest_runtest_teardown(item: object) -> None:
    global _DNS_ORIGINAL  # noqa: PLW0603
    marker = getattr(item, "get_closest_marker", lambda _name: None)("dns_fallback")
    if marker is None or _DNS_ORIGINAL is None:
        return
    from ar_common import egress_http  # noqa: PLC0415

    egress_http.resolve_host = _DNS_ORIGINAL  # type: ignore[assignment]
    _DNS_ORIGINAL = None


def pytest_addoption(parser: object) -> None:
    """Register ``--with-qdrant`` for the optional retrieval adapter."""
    parser.addoption("--with-qdrant", action="store_true", default=False)  # type: ignore[attr-defined]
