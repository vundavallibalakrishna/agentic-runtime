"""Session-scoped Postgres and Valkey containers."""

from typing import TYPE_CHECKING

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from collections.abc import Iterator

PG_IMAGE = "pgvector/pgvector:0.8.7-pg18-trixie"
VALKEY_IMAGE = "valkey/valkey:9.1.2"


def to_libpq_url(url: str) -> str:
    """Drop a SQLAlchemy driver suffix so psycopg can parse the URL.

    ``PostgresContainer(driver="psycopg")`` yields ``postgresql+psycopg://...``.
    libpq rejects that scheme (``missing "="``).
    """
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    scheme = scheme.split("+", 1)[0]
    if scheme == "postgres":
        scheme = "postgresql"
    return f"{scheme}://{rest}"


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Yield a SQLAlchemy-style URL for a disposable Postgres + pgvector database."""
    with PostgresContainer(PG_IMAGE, driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def valkey_url() -> Iterator[str]:
    """Yield a Redis URL for a disposable Valkey container."""
    container = DockerContainer(VALKEY_IMAGE).with_exposed_ports(6379)
    container.start()
    wait_for_logs(container, "Ready to accept connections", timeout=60)
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    try:
        yield f"redis://{host}:{port}/0"
    finally:
        container.stop()
