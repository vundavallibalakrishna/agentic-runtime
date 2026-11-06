"""File bytes live in the object store; the product never keeps them anywhere else.

Task: M38b-T13. The integration test of the same name proves it on Postgres and SeaweedFS;
this one covers what needs no server: the stand-in is registered by the test, a store that
is down is reported in words that name the setting, and a cache that is trimmed loses
nothing.
"""

import uuid

import pytest

from ar_common.errors import ArError
from ar_domain.chat.eviction import evict_chat_cache
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durability.store import read_blob
from ar_domain.files.objects import object_store
from ar_testing.demo import demo_store
from ar_testing.objects import MemoryObjectStore, RefusingObjectStore

TENANT = demo_id("tenant")
ADMIN = demo_id("admin")


def test_an_upload_is_one_object_under_the_rows_key() -> None:
    store = demo_store()
    objects = object_store(store)
    assert isinstance(objects, MemoryObjectStore), "the test's setup registered it"
    uploaded = store.upload(TENANT, ADMIN, "note.txt", "text/plain", b"hello object")
    file_id = uuid.UUID(str(uploaded["id"]))
    key = str(store.files[file_id]["object_key"])
    assert objects.objects[key] == (b"hello object", "text/plain")
    assert objects.puts == 1
    # Trimming the cache loses nothing: the next read comes from the store.
    store.blobs.clear()
    assert read_blob(store, file_id) == b"hello object"
    assert store.file_bytes(TENANT, ADMIN, file_id) == (b"hello object", "text/plain")


def test_a_store_that_is_down_is_named_and_nothing_is_kept() -> None:
    store = demo_store()
    store.objects = RefusingObjectStore("http://objects.example:9000")
    before = set(store.files)
    with pytest.raises(ArError, match=r"objects\.example:9000") as refused:
        store.upload(TENANT, ADMIN, "note.txt", "text/plain", b"hello")
    assert "AR_S3_ENDPOINT" in str(refused.value)
    assert refused.value.code.value == "unavailable"
    assert set(store.files) == before


def test_the_product_store_builds_the_configured_bucket_client() -> None:
    from ar_common.s3 import S3Store

    store = ChatService()
    assert store.objects is None, "the product does not come with a stand-in"
    assert isinstance(object_store(store), S3Store)


def test_the_cache_is_trimmed_oldest_first_and_the_store_still_has_every_file() -> None:
    store = demo_store()
    ids = [
        uuid.UUID(str(store.upload(TENANT, ADMIN, f"f{n}.txt", "text/plain", bytes(n + 1))["id"]))
        for n in range(4)
    ]
    store.blobs = {file_id: store.blobs[file_id] for file_id in ids}
    store.cache_limits = {"blobs_bytes": 5}
    removed = evict_chat_cache(store)
    assert removed["blobs"] >= 1
    assert ids[-1] in store.blobs, "the newest stays"
    assert all(read_blob(store, file_id) == bytes(n + 1) for n, file_id in enumerate(ids))


def test_a_deleted_file_is_not_read_back() -> None:
    store = demo_store()
    uploaded = store.upload(TENANT, ADMIN, "note.txt", "text/plain", b"gone soon")
    file_id = uuid.UUID(str(uploaded["id"]))
    store.delete_file(TENANT, ADMIN, file_id)
    assert store.files[file_id]["status"] == "deleted"
    assert store.files[file_id]["deleted_at"] is not None
    assert read_blob(store, file_id) is None
