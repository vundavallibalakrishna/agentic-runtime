"""URL helpers for disposable databases."""

from ar_testing.containers import to_libpq_url


def test_to_libpq_url_strips_sqlalchemy_driver() -> None:
    assert (
        to_libpq_url("postgresql+psycopg://test:test@localhost:1/test")
        == "postgresql://test:test@localhost:1/test"
    )


def test_to_libpq_url_normalizes_postgres_scheme() -> None:
    assert to_libpq_url("postgres://localhost/db") == "postgresql://localhost/db"


def test_to_libpq_url_leaves_non_urls() -> None:
    assert to_libpq_url("not-a-url") == "not-a-url"
