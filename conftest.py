"""Root pytest plugins."""

pytest_plugins = [
    "ar_testing.containers",
    "ar_testing.temporal",
    "ar_testing.fake_llm",
    "ar_testing.auth",
]


def pytest_addoption(parser: object) -> None:
    """Register ``--with-qdrant`` for the optional retrieval adapter."""
    parser.addoption("--with-qdrant", action="store_true", default=False)  # type: ignore[attr-defined]
