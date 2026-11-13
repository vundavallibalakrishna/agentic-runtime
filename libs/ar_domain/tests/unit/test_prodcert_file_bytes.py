"""Production-cert defect 5: file bytes are stored durably, not in process memory.

`identity/data_rights.export_user` and `sandboxes/service.seed_chart` used to write
their bytes into ``store.blobs`` (a bounded in-process cache), so in production the
bytes were gone after the request. Both now write through the object store. The proof
clears the cache and reads the bytes back, which forces a read from the store. Unit.
"""

import io
import uuid
import zipfile

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.durability.store import read_blob
from ar_domain.identity.data_rights import export_user
from ar_domain.sandboxes.service import SandboxBook
from ar_testing.demo import demo_store


def test_export_user_stores_the_zip_durably() -> None:
    store = demo_store()
    actor = Actor(demo_id("tenant"), demo_id("admin"), frozenset())

    result = export_user(store, actor)
    export_id = uuid.UUID(str(result["export_id"]))
    assert result["status"] == "ready"

    # Not bytes in this process: clear the cache, so a read must come from the store.
    store.blobs.clear()
    data = read_blob(store, export_id)
    assert data is not None and data[:2] == b"PK"  # a real zip archive
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert "profile.json" in archive.namelist()
    row = store.files[export_id]
    assert row["kind"] == "export" and row["object_key"]


def test_seed_chart_stores_the_png_durably() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    store.agents[demo_id("revenue-analyst")] = {
        "id": demo_id("revenue-analyst"),
        "tenant_id": tenant,
        "slug": "revenue-analyst",
        "name": "Revenue Analyst",
        "published_version_id": None,
    }

    SandboxBook(store).seed_chart(tenant, user)
    file_id = demo_id("showcase-revenue-png")
    assert file_id in store.files

    # The preview survives even when the in-process cache is empty.
    store.blobs.clear()
    png = read_blob(store, file_id)
    assert png is not None and png[:4] == b"\x89PNG"
