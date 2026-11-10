"""Cover the pack loader, erasure locks, sheet grids and rule-set judgements."""

from __future__ import annotations

import base64
import io
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any

import orjson
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from ar_common.errors import ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import manifest_digest
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.erasure import erase_user
from ar_domain.packs import hooks
from ar_domain.packs.loader import load_manifest, load_pack_tree
from ar_domain.records.locks import is_held
from ar_domain.records.memory import bucket
from ar_domain.spreadsheet.grid import grids_from_xlsx

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


class _App:
    def __init__(self) -> None:
        self.mounted: list[str] = []


def _key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _write_manifest(pack: Path, manifest: dict[str, object]) -> dict[str, object]:
    path = pack / "manifest.json"
    path.write_bytes(orjson.dumps(manifest))
    loaded = orjson.loads(path.read_bytes())
    assert isinstance(loaded, dict)
    return loaded


def _sign(pack: Path, manifest: dict[str, object], private: Ed25519PrivateKey) -> None:
    _digest, raw = manifest_digest(manifest)
    signature = base64.b64encode(private.sign(raw)).decode()
    (pack / "signature.b64").write_text(f"{signature}\n", encoding="utf-8")
    public = private.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    (pack / "key.pub").write_text(public.decode(), encoding="utf-8")


def _pack(root: Path, name: str, manifest: dict[str, object]) -> tuple[Path, dict[str, object]]:
    pack = root / name
    pack.mkdir()
    loaded = _write_manifest(pack, manifest)
    return pack, loaded


def test_loader_skips_a_missing_directory(tmp_path: Path) -> None:
    load_pack_tree(_App(), tmp_path / "absent", require_signature=True)
    load_pack_tree(_App(), tmp_path, require_signature=False)


def test_loader_rejects_a_manifest_that_is_not_an_object(tmp_path: Path) -> None:
    pack = tmp_path / "bad"
    pack.mkdir()
    (pack / "manifest.json").write_bytes(b"[]")
    with pytest.raises(TypeError):
        load_manifest(_App(), pack / "manifest.json", require_signature=False)


def test_loader_refuses_an_unsigned_pack_when_signatures_are_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack, _loaded = _pack(tmp_path, "plain", {"spec": {}})
    load_manifest(_App(), pack / "manifest.json", require_signature=False)
    with pytest.raises(ValueError, match="unsigned"):
        load_manifest(_App(), pack / "manifest.json", require_signature=True)
    monkeypatch.setenv("AR_PACK_SIGNATURE_REQUIRED", "1")
    with pytest.raises(ValueError, match="unsigned"):
        load_manifest(_App(), pack / "manifest.json", require_signature=False)
    (pack / "signature.b64").write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsigned"):
        load_manifest(_App(), pack / "manifest.json", require_signature=True)


def test_loader_rejects_a_signature_without_a_key_or_a_bad_signature(tmp_path: Path) -> None:
    pack, loaded = _pack(tmp_path, "signed", {"spec": {"extension": "nope"}})
    private = _key()
    _sign(pack, loaded, private)
    (pack / "key.pub").unlink()
    with pytest.raises(ValueError, match="public key"):
        load_manifest(_App(), pack / "manifest.json", require_signature=True)
    _sign(pack, loaded, private)
    bogus = base64.b64encode(b"not-a-signature").decode()
    (pack / "signature.b64").write_text(bogus, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        load_manifest(_App(), pack / "manifest.json", require_signature=False)


def test_loader_rejects_an_untrusted_key_and_mounts_a_trusted_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _key()
    pack, loaded = _pack(
        tmp_path,
        "demo",
        {"spec": {"extension": {"entry": "stage2_probe_mount"}}},
    )
    _sign(pack, loaded, private)
    (pack / "key.id").write_text("demo-example\n", encoding="utf-8")
    src = pack / "src"
    src.mkdir()
    (src / "stage2_probe_mount.py").write_text(
        "def mount(app):\n    app.mounted.append('demo')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AR_PACK_TRUSTED_KEYS", "other-example")
    with pytest.raises(ValueError, match="not trusted"):
        load_manifest(_App(), pack / "manifest.json", require_signature=True)
    monkeypatch.setenv("AR_PACK_TRUSTED_KEYS", "demo-example")
    app = _App()
    load_pack_tree(app, tmp_path, require_signature=True)
    assert app.mounted == ["demo"]
    assert str(src) not in sys.path
    sys.modules.pop("stage2_probe_mount", None)


def test_loader_imports_a_module_already_on_the_path(tmp_path: Path) -> None:
    private = _key()
    pack, loaded = _pack(
        tmp_path, "ready", {"spec": {"extension": {"entry": "stage2_probe_nomount"}}}
    )
    _sign(pack, loaded, private)
    src = pack / "src"
    src.mkdir()
    (src / "stage2_probe_nomount.py").write_text("VALUE = 1\n", encoding="utf-8")
    sys.path.insert(0, str(src))
    try:
        load_manifest(_App(), pack / "manifest.json", require_signature=False)
    finally:
        sys.path.remove(str(src))
        sys.modules.pop("stage2_probe_nomount", None)


def test_loader_removes_the_path_when_import_fails(tmp_path: Path) -> None:
    private = _key()
    pack, loaded = _pack(
        tmp_path, "missing", {"spec": {"extension": {"entry": "stage2_probe_missing"}}}
    )
    _sign(pack, loaded, private)
    src = pack / "src"
    src.mkdir()
    with pytest.raises(ModuleNotFoundError):
        load_manifest(_App(), pack / "manifest.json", require_signature=False)
    assert str(src) not in sys.path


def test_loader_stops_when_the_manifest_names_no_entry(tmp_path: Path) -> None:
    private = _key()
    pack, loaded = _pack(tmp_path, "quiet", {"spec": {"extension": {}}})
    _sign(pack, loaded, private)
    load_manifest(_App(), pack / "manifest.json", require_signature=False)
    bare, bare_loaded = _pack(tmp_path, "bare", {"name": "bare"})
    _sign(bare, bare_loaded, private)
    load_manifest(_App(), bare / "manifest.json", require_signature=True)


def test_review_hook_can_pause_delivery() -> None:
    def skip(_store: object, _routine: object, _target: object) -> None:
        return None

    def hold(_store: object, _routine: object, _target: object) -> dict[str, str]:
        return {"status": "waiting"}

    before = list(hooks._review)
    hooks.register_review_hook(skip)
    hooks.register_review_hook(hold)
    hooks.register_review_hook(hold)
    try:
        assert hooks.review_delivery(object(), {"id": "routine"}, {"id": "target"}) == {
            "status": "waiting"
        }
    finally:
        hooks._review[:] = before


def test_is_held_is_true_only_for_an_active_hold() -> None:
    store = _memory_store()
    record_id = uuid.uuid4()
    active = uuid.uuid4()
    released = uuid.uuid4()
    bucket(store, "holds")[released] = {"status": "released"}
    bucket(store, "holds")["bad"] = "not-a-hold"  # type: ignore[assignment]
    bucket(store, "holds")[active] = {"status": "active"}
    members = bucket(store, "hold_members")
    members["other"] = {"record_class": "file", "record_id": record_id, "hold_id": active}
    members["released"] = {
        "record_class": "conversation",
        "record_id": record_id,
        "hold_id": released,
    }
    members["bad"] = {"record_class": "conversation", "record_id": record_id, "hold_id": "bad"}
    assert is_held(store, "conversation", record_id) is False
    members["active"] = {
        "record_class": "conversation",
        "record_id": record_id,
        "hold_id": active,
    }
    assert is_held(store, "conversation", record_id) is True


def test_erase_user_skips_held_rows_and_deletes_the_rest() -> None:
    store = _memory_store()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    other = uuid.uuid4()
    actor = Actor(tenant_id=tenant, user_id=other, permissions=frozenset({"users:manage"}))
    held_conversation = uuid.uuid4()
    free_conversation = uuid.uuid4()
    held_file = uuid.uuid4()
    free_file = uuid.uuid4()
    fact = uuid.uuid4()
    hold_id = uuid.uuid4()
    bucket(store, "holds")[hold_id] = {"status": "active"}
    members = bucket(store, "hold_members")
    members[uuid.uuid4()] = {
        "record_class": "conversation",
        "record_id": held_conversation,
        "hold_id": hold_id,
    }
    members[uuid.uuid4()] = {
        "record_class": "file",
        "record_id": held_file,
        "hold_id": hold_id,
    }
    store.conversations["nope"] = "not-a-row"
    store.conversations[uuid.uuid4()] = {"tenant_id": uuid.uuid4(), "user_id": user}
    store.conversations[uuid.uuid4()] = {"tenant_id": tenant, "user_id": other}
    store.conversations[held_conversation] = {"tenant_id": tenant, "user_id": user}
    store.conversations[free_conversation] = {"tenant_id": tenant, "owner_user_id": user}
    message_id = uuid.uuid4()
    kept_message = uuid.uuid4()
    store.messages[message_id] = {"conversation_id": free_conversation}
    store.messages[kept_message] = {"conversation_id": held_conversation}
    store.messages["note"] = "skip"
    run_id = uuid.uuid4()
    store.runs[run_id] = {"conversation_id": free_conversation}
    store.runs[uuid.uuid4()] = {"conversation_id": held_conversation}
    store.runs["skip"] = "nope"
    store.files[held_file] = {"tenant_id": tenant, "uploaded_by": user}
    store.files[free_file] = {"tenant_id": tenant, "uploaded_by": user}
    store.blobs[free_file] = b"bytes"
    store.blobs[held_file] = b"kept"
    store.memory_facts[fact] = {"tenant_id": tenant, "user_id": user}
    store.memory_facts[uuid.uuid4()] = {"tenant_id": tenant, "user_id": other}
    grant_id = uuid.uuid4()
    store.credential_grants[grant_id] = {"user_id": user}
    store.credential_grants[uuid.uuid4()] = {"user_id": other}
    store.credential_grants["skip"] = "nope"
    identity_id = uuid.uuid4()
    store.channel_identities[identity_id] = {"user_id": user, "tenant_id": tenant}
    store.channel_identities[uuid.uuid4()] = {"user_id": user, "tenant_id": other}
    points = bucket(store, "retrieval_points")
    held_point = uuid.uuid4()
    free_point = uuid.uuid4()
    points[held_point] = {"user_id": user, "held": True}
    points[free_point] = {"user_id": user}
    points["skip"] = "nope"
    points[uuid.uuid4()] = {"user_id": other}

    detail = erase_user(store, actor, user)

    assert held_conversation in store.conversations
    assert free_conversation not in store.conversations
    assert message_id not in store.messages
    assert kept_message in store.messages
    assert run_id not in store.runs
    assert held_file in store.files
    assert free_file not in store.files
    assert free_file not in store.blobs
    assert store.blobs[held_file] == b"kept"
    assert fact not in store.memory_facts
    assert grant_id not in store.credential_grants
    assert identity_id not in store.channel_identities
    assert held_point in points
    assert free_point not in points
    assert detail["removed"] == 3
    assert str(held_conversation) in detail["held_record_ids"]
    assert str(held_point) in detail["held_record_ids"]
    assert store.audit_log[-1]["action"] == "erasure.completed"


def test_erase_user_ignores_missing_edge_maps() -> None:
    store = _memory_store()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    actor = Actor(tenant_id=tenant, user_id=user, permissions=frozenset({"users:manage"}))
    store.credential_grants = None
    store.channel_identities = None
    detail = erase_user(store, actor, user)
    assert detail["removed"] == 0


def test_grids_keep_header_text_and_skip_missing_sheets() -> None:
    assert grids_from_xlsx(_zip({"[Content_Types].xml": "<Types/>"})) == []
    long_name = "H" * 130
    data = (
        f'<worksheet xmlns="{_NS}"><sheetData>'
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>Name</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t> </t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Name</t></is></c>'
        f'<c r="D1" t="inlineStr"><is><t>{long_name}</t></is></c>'
        "</row>"
        '<row r="2"><c r="A2" t="inlineStr"><is><t>only</t></is></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>extra</t></is></c></row>'
        "</sheetData></worksheet>"
    )
    empty = f'<worksheet xmlns="{_NS}"><sheetData></sheetData></worksheet>'
    workbook = (
        f'<workbook xmlns="{_NS}" xmlns:r="{_OFFICE}"><sheets>'
        '<sheet name="Empty" sheetId="1" r:id="rId1"/>'
        '<sheet name="Gone" sheetId="2" r:id="rId2"/>'
        '<sheet name="Data" sheetId="3" r:id="rId3"/>'
        "</sheets></workbook>"
    )
    rels = (
        f'<Relationships xmlns="{_PKG}">'
        '<Relationship Id="rId1" Type="worksheet" Target="worksheets/empty.xml"/>'
        '<Relationship Id="rId2" Type="worksheet" Target="worksheets/gone.xml"/>'
        '<Relationship Id="rId3" Type="worksheet" Target="worksheets/data.xml"/>'
        "</Relationships>"
    )
    grids = grids_from_xlsx(
        _zip(
            {
                "xl/workbook.xml": workbook,
                "xl/_rels/workbook.xml.rels": rels,
                "xl/worksheets/empty.xml": empty,
                "xl/worksheets/data.xml": data,
            }
        ),
        max_rows=1,
    )
    assert len(grids) == 1
    grid = grids[0]
    assert grid.name == "Data"
    assert grid.columns[0] == "Name"
    assert grid.columns[1] == "Column 2"
    assert grid.columns[2] == "Name 2"
    assert len(grid.columns[3]) == 120
    assert grid.rows == (("only", "", "", ""),)


def test_judge_stores_a_rule_set_and_reads_it_back() -> None:
    store = _document_store()
    library = DocumentLibrary(store)
    actor = Actor(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset())
    source = library.ingest(
        actor,
        data=b"# Access\n\n- Badges are required\n",
        filename="access.md",
    )
    subject = library.ingest(
        actor,
        data=b"# Travel\n\nTrips need approval.\n",
        filename="travel.md",
    )
    source_id = uuid.UUID(str(source["id"]))
    subject_id = uuid.UUID(str(subject["id"]))
    with pytest.raises(ValidationFailedError):
        library.judge(actor, subject_id, statements=["  "])
    library.judge(
        actor,
        subject_id,
        statements=["Trips need approval"],
        rule_set={"items": []},
    )
    report = library.judge(
        actor,
        subject_id,
        statements=["  ", "Trips need approval"],
        rule_set={
            "id": "access-rules",
            "version": "3",
            "items": [{"statement": "Badges are required"}, "Visitors sign in", "", 4],
            "source_file_id": source_id,
            "sha256": "abc",
        },
    )
    assert report["rule_set_version"] == "3"
    assert report["kind"] == "judge"
    assert bucket(store, "rule_sets")["access-rules"]["sha256"] == "abc"
    bucket(store, "rule_sets")["broken"] = "nope"  # type: ignore[assignment]
    library.judge(actor, subject_id, statements=["Trips need approval"], rule_set_id="broken")
    named = library.missing(
        actor,
        subject_id,
        statements=["Trips need approval"],
        rule_set={
            "id": "travel-rules",
            "version": "1",
            "items": "not-a-list",
            "sourceFileId": "not-a-uuid",
            "sha256": "",
        },
    )
    assert named["rule_set_id"] == "travel-rules"
    again = library.judge(actor, subject_id, statements=[], rule_set_id="travel-rules")
    assert again["rule_set_id"] == "travel-rules"
    rows = again["rows"]
    assert isinstance(rows, list)
    assert rows


def _memory_store() -> Any:
    class Store:
        def __init__(self) -> None:
            self.conversations: dict[object, object] = {}
            self.files: dict[object, object] = {}
            self.memory_facts: dict[object, object] = {}
            self.messages: dict[object, object] = {}
            self.runs: dict[object, object] = {}
            self.blobs: dict[object, bytes] = {}
            self.credential_grants: object = {}
            self.channel_identities: object = {}
            self.audit_log: list[dict[str, object]] = []
            self.domain_events: list[dict[str, object]] = []

    return Store()


def _document_store() -> Any:
    class Store:
        def __init__(self) -> None:
            self.scanner = "none"
            self.audit_log: list[dict[str, object]] = []

    return Store()


def _zip(parts: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        for name, payload in parts.items():
            book.writestr(name, payload)
    return buffer.getvalue()
