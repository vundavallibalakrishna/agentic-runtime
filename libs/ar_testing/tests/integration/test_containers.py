"""Sample integration test. Spec: M0-T12."""

import psycopg
import pytest
import redis

from ar_testing.containers import to_libpq_url


@pytest.mark.integration
def test_postgres_and_valkey_round_trip(postgres_url: str, valkey_url: str) -> None:
    """Postgres accepts a query and Valkey stores a key."""
    with psycopg.connect(to_libpq_url(postgres_url)) as connection:
        row = connection.execute("SELECT 1").fetchone()
    assert row is not None
    assert row[0] == 1
    client = redis.Redis.from_url(valkey_url)
    client.set("ar:sample", "ok")
    assert client.get("ar:sample") == b"ok"
