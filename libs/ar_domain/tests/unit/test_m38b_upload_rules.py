"""What a person may attach is the organisation's setting (M38b-T08a, finding F51).

The upload path used a list and a size written into the code, while the settings for both
existed and were never read. The composer offered a shorter list of its own.
"""

from __future__ import annotations

import uuid

import pytest

from ar_common.errors import ArError
from ar_contracts.tenants import READABLE_UPLOAD_MIME_TYPES, TenantSettings
from ar_domain.demo_ids import demo_id
from ar_domain.files.logic import MAX_UPLOAD_BYTES, typed_by_name, upload_rules
from ar_testing.demo import demo_store

TENANT = demo_id("tenant")
USER = demo_id("admin")


def test_the_default_is_every_type_the_product_can_read() -> None:
    rules = upload_rules({})
    assert set(rules.mime_types) == set(READABLE_UPLOAD_MIME_TYPES)
    for mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/markdown",
        "image/webp",
    ):
        assert rules.allows(mime)
    assert not rules.allows("application/x-msdownload")
    assert rules.max_bytes == 25 * 1024 * 1024
    assert TenantSettings().security.allowed_upload_mime_types == list(READABLE_UPLOAD_MIME_TYPES)


def test_the_organisation_narrows_the_types_and_the_size() -> None:
    rules = upload_rules(
        {"security": {"allowed_upload_mime_types": ["application/PDF"], "max_upload_mb": 2}}
    )
    assert rules.mime_types == ("application/pdf",)
    assert rules.allows("application/pdf")
    assert not rules.allows("text/csv")
    assert rules.max_bytes == 2 * 1024 * 1024
    # The product keeps at most 25 MB for a file today, whatever the setting says.
    assert upload_rules({"security": {"max_upload_mb": 500}}).max_bytes == MAX_UPLOAD_BYTES


def test_a_file_the_browser_gave_no_type_is_typed_by_its_name() -> None:
    assert typed_by_name("notes.md", "") == "text/markdown"
    assert typed_by_name("sheet.xlsx", "application/octet-stream") == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert typed_by_name("orders.csv", "text/csv") == "text/csv"
    assert typed_by_name("data", "") == ""


def test_an_upload_follows_the_calling_tenants_rules() -> None:
    store = demo_store()
    store.tenant_settings[TENANT] = {
        "security": {"allowed_upload_mime_types": ["text/csv"], "max_upload_mb": 1}
    }
    saved = store.upload(TENANT, USER, "orders.csv", "", b"a,b\n")
    assert saved["mime_type"] == "text/csv"
    with pytest.raises(ArError) as refused:
        store.upload(TENANT, USER, "notes.pdf", "application/pdf", b"%PDF-1.4")
    assert "application/pdf cannot be attached here" in str(refused.value)
    assert "organisation's settings" in str(refused.value)
    with pytest.raises(ArError) as too_big:
        store.upload(TENANT, USER, "big.csv", "text/csv", b"x" * (1024 * 1024 + 1))
    assert "over the 1 MB limit" in str(too_big.value)
    assert store.upload_limits(TENANT) == {"mime_types": ["text/csv"], "max_bytes": 1024 * 1024}
    # Another tenant keeps the default.
    other = uuid.uuid4()
    assert len(store.upload_limits(other)["mime_types"]) == len(READABLE_UPLOAD_MIME_TYPES)


def test_a_message_records_each_files_size_with_its_name_and_type() -> None:
    store = demo_store()
    conversation_id = uuid.UUID(str(store.create_conversation(TENANT, USER, None)["id"]))
    one = store.upload(TENANT, USER, "orders.csv", "text/csv", b"a,b\n1,2\n")
    two = store.upload(TENANT, USER, "notes.md", "", b"# Notes\n")
    posted = store.post_message(
        TENANT,
        USER,
        conversation_id,
        "Read these",
        attachment_ids=[uuid.UUID(str(one["id"])), uuid.UUID(str(two["id"]))],
        schedule=False,
    )
    parts = [part for part in posted["message"]["content"] if part["type"] == "file"]
    assert parts == [
        {
            "type": "file",
            "file_id": str(one["id"]),
            "name": "orders.csv",
            "mime_type": "text/csv",
            "size_bytes": 8,
        },
        {
            "type": "file",
            "file_id": str(two["id"]),
            "name": "notes.md",
            "mime_type": "text/markdown",
            "size_bytes": 8,
        },
    ]
