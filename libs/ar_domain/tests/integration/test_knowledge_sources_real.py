"""Knowledge sources against a real object store and a real database. OQ-197.

The unit tests drive the same code with services a test owns. These two run it against
the object store the stack bundles (S3 API) and a Postgres server, so the calls the
product makes (``ListObjectsV2``, ``GetObject``, a read-only query) are the ones a real
service answers.
"""

from __future__ import annotations

import uuid

import pytest

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.syncing import sync_source
from ar_domain.tools.data_connections import DataConnections
from ar_domain.tools.service_connections import ConnectionBook
from ar_testing.containers import to_libpq_url
from ar_testing.demo import demo_store

pytestmark = pytest.mark.integration

_ACCESS_KEY = "knowledge-source-test"
_SECRET_KEY = "knowledge-source-test-secret"  # noqa: S105 — the object store in the test takes any key


def _admin() -> Actor:
    return Actor(
        demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, roles=frozenset({"tenant_admin"})
    )


def _collection(store: ChatService, slug: str) -> uuid.UUID:
    created = KnowledgeBook(store).create_collection(
        _admin(), {"slug": slug, "name": slug, "acl_mode": "collection"}
    )
    return uuid.UUID(str(created["id"]))


def _titles(store: ChatService, collection_id: uuid.UUID) -> set[str]:
    return {
        str(row["title"])
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection_id and row.get("status") != "deleted"
    }


def test_an_s3_source_indexes_a_real_bucket_and_follows_a_delete(s3_endpoint: str) -> None:
    import boto3

    bucket = f"kn-{uuid.uuid4().hex[:12]}"
    client = boto3.client(
        "s3",
        endpoint_url=s3_endpoint,
        region_name="us-east-1",
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
    )
    client.create_bucket(Bucket=bucket)
    client.put_object(
        Bucket=bucket, Key="handbook/visitors.md", Body=b"# Visitors\n\nThe desk opens at 08:30."
    )
    client.put_object(
        Bucket=bucket, Key="handbook/payroll.md", Body=b"# Payroll\n\nReleased on the 28th."
    )
    client.put_object(Bucket=bucket, Key="other/notes.md", Body=b"Not under the prefix.")

    store = demo_store()
    ConnectionBook(store).create(
        _admin(),
        {"name": "bucket-keys", "kind": "basic", "username": _ACCESS_KEY, "secret": _SECRET_KEY},
    )
    collection_id = _collection(store, "real-bucket")
    source = KnowledgeBook(store).create_source(
        _admin(),
        collection_id,
        {
            "name": "Handbook",
            "kind": "s3",
            "config": {
                "endpoint": s3_endpoint,
                "bucket": bucket,
                "prefix": "handbook/",
                "connection": "bucket-keys",
            },
        },
    )
    assert source["last_sync_status"] == "succeeded", store.knowledge_jobs
    assert _titles(store, collection_id) == {"visitors.md", "payroll.md"}
    found = KnowledgeBook(store).search(
        _admin(), {"query": "desk opens", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "visitors.md" for hit in found["hits"])

    client.delete_object(Bucket=bucket, Key="handbook/payroll.md")
    row = store.knowledge_sources[uuid.UUID(str(source["id"]))]
    job = sync_source(store, row, mode="incremental", actor_id=_admin().user_id)
    assert job["status"] == "succeeded"
    assert _titles(store, collection_id) == {"visitors.md"}


def test_a_database_source_indexes_the_rows_a_real_query_returns(postgres_url: str) -> None:
    import psycopg

    table = f"kn_articles_{uuid.uuid4().hex[:8]}"
    dsn = to_libpq_url(postgres_url)
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(
            f"CREATE TABLE {table} (id int PRIMARY KEY, title text, body text, readers text)"
        )
        connection.execute(
            f"INSERT INTO {table} VALUES "  # noqa: S608 — the table name is made in this test
            "(1, 'Visitor desk', 'The visitor desk opens at 08:30.', 'admin@dev.local'), "
            "(2, 'Payroll', 'Payroll is released on the 28th.', 'member@dev.local')"
        )

    # The server is shared with the migration tests, which compare its tables with the
    # models: the table made here is dropped whatever happens.
    try:
        store = demo_store()
        store.user_emails[demo_id("admin")] = "admin@dev.local"
        store.user_emails[demo_id("member")] = "member@dev.local"
        store.company_domains = {"dev.local"}
        connection_row = DataConnections(store).create(
            _admin(), {"name": "articles", "engine": "postgres", "dsn": dsn}
        )
        created = KnowledgeBook(store).create_collection(
            _admin(), {"slug": "real-rows", "name": "Rows", "acl_mode": "source"}
        )
        collection_id = uuid.UUID(str(created["id"]))
        source = KnowledgeBook(store).create_source(
            _admin(),
            collection_id,
            {
                "name": "Articles",
                "kind": "database",
                "data_connection_id": str(connection_row["id"]),
                "config": {
                    "query": f"SELECT id, title, body, readers FROM {table}",  # noqa: S608
                    "textColumn": "body",
                    "aclColumn": "readers",
                },
            },
        )
        assert source["last_sync_status"] == "succeeded", store.knowledge_jobs
        assert _titles(store, collection_id) == {"Visitor desk", "Payroll"}
        # Each row's readers column decides who finds it: the admin is on the first row only.
        seen = KnowledgeBook(store).search(
            _admin(), {"query": "visitor desk payroll", "collection_ids": [collection_id]}
        )
        assert {hit["title"] for hit in seen["hits"]} == {"Visitor desk"}
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(f"DROP TABLE IF EXISTS {table}")
