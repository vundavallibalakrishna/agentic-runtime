"""Binder export. Spec: docs/03-specs/21-records-governance.md §5."""

from __future__ import annotations

import hashlib
import io
import os
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.jcs import canonical_json
from ar_common.time import utcnow
from ar_domain.records.access import audit, missing, own, public, require
from ar_domain.records.crypto import public_pem, sign_manifest, signing_material
from ar_domain.records.memory import blobs, bucket

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_CAP = 5000


class BinderBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_binders(self, actor: Actor) -> list[dict[str, object]]:
        rows = []
        for row in bucket(self.store, "binders").values():
            if not own(row, actor.tenant_id):
                continue
            if actor.kind == "guest":
                if not _guest_binder(self.store, actor, row.get("id")):
                    continue
            elif not actor.has("binders:export") and row.get("created_by") != actor.user_id:
                continue
            rows.append(public(row))
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return rows

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        require(actor, "binders:export")
        raw_selection = body.get("selection")
        selection: dict[str, object] = raw_selection if isinstance(raw_selection, dict) else {}
        if _count(selection) > _limit():
            raise ArError(ErrorCode.BINDER_TOO_LARGE, "binder_too_large")
        binder_id = new_id()
        now = utcnow()
        row = {
            "id": binder_id,
            "tenant_id": actor.tenant_id,
            "title": str(body.get("title") or "Binder"),
            "status": "draft",
            "selection": selection,
            "require_review": bool(body.get("require_review")),
            "review_item_id": None,
            "manifest_sha256": None,
            "file_id": None,
            "created_by": actor.user_id,
            "created_at": now,
            "completed_at": None,
        }
        bucket(self.store, "binders")[binder_id] = row
        audit(self.store, actor, "binder.created", "binder", binder_id, {"title": row["title"]})
        return public(row)

    def get(self, actor: Actor, binder_id: uuid.UUID) -> dict[str, object]:
        return public(self._visible(actor, binder_id))

    def build(self, actor: Actor, binder_id: uuid.UUID) -> dict[str, object]:
        require(actor, "binders:export")
        row = self._visible(actor, binder_id)
        if row.get("require_review") and not _signed(self.store, row.get("review_item_id")):
            if row.get("review_item_id") is None:
                item_id = new_id()
                self.store.review_items[item_id] = {
                    "id": item_id,
                    "tenant_id": actor.tenant_id,
                    "subject_type": "binder",
                    "subject_id": binder_id,
                    "status": "pending",
                    "content_hash": "",
                }
                row["review_item_id"] = item_id
                row["status"] = "pending_review"
            raise ArError(ErrorCode.REVIEW_REQUIRED, "review_required")
        payload = build_zip(self.store, row)
        file_id = new_id()
        self.store.files[file_id] = {
            "id": file_id,
            "tenant_id": actor.tenant_id,
            "name": f"{row['title']}.zip",
            "mime_type": "application/zip",
            "kind": "export",
            "user_id": actor.user_id,
            "created_at": utcnow(),
        }
        self.store.blobs[file_id] = payload
        digest = hashlib.sha256(payload).hexdigest()
        row["status"] = "ready"
        row["file_id"] = file_id
        row["manifest_sha256"] = digest
        row["completed_at"] = utcnow()
        blobs(self.store, "binders")[binder_id] = payload
        audit(self.store, actor, "binder.built", "binder", binder_id, {"manifest_sha256": digest})
        self.store.domain_events.append(
            {
                "topic": "binder.ready",
                "payload": {"binder_id": str(binder_id)},
                "at": utcnow().isoformat(),
            }
        )
        return public(row)

    def download(self, actor: Actor, binder_id: uuid.UUID) -> bytes:
        row = self._visible(actor, binder_id)
        data = blobs(self.store, "binders").get(binder_id)
        if not isinstance(data, bytes):
            file_id = row.get("file_id")
            stored = self.store.blobs.get(file_id) if file_id is not None else None
            if not isinstance(stored, bytes):
                raise NotFoundError()
            data = stored
        audit(self.store, actor, "binder.downloaded", "binder", binder_id, {})
        if actor.kind == "guest":
            audit(self.store, actor, "guest.downloaded", "binder", binder_id, {})
        return data

    def _visible(self, actor: Actor, binder_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "binders").get(binder_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            missing()
        if actor.kind == "guest":
            if not _guest_binder(self.store, actor, binder_id):
                missing()
            return row
        if actor.has("binders:export") or row.get("created_by") == actor.user_id:
            return row
        missing()
        return row


def build_zip(store: Any, row: dict[str, object]) -> bytes:
    """ZIP with a manifest, a text index and the stdlib verifier."""
    raw_selection = row.get("selection")
    selection: dict[str, object] = raw_selection if isinstance(raw_selection, dict) else {}
    files: dict[str, bytes] = {}
    files["index.pdf"] = _pdf(str(row.get("title") or "Binder"))
    files["index.xlsx"] = _xlsx(selection)
    raw_ids = selection.get("evidence_ids")
    evidence_ids: list[object] = []
    if isinstance(raw_ids, list):
        evidence_ids.extend(raw_ids)
    for raw in evidence_ids:
        item_id = uuid.UUID(str(raw))
        item = bucket(store, "evidence").get(item_id)
        blob = blobs(store, "evidence").get(item_id, b"")
        if isinstance(item, dict):
            files[f"records/evidence_item/{item_id}.json"] = canonical_json(
                cast("JsonValue", public(item))
            )
            files[f"evidence/{item_id}.bin"] = blob if isinstance(blob, bytes) else b""
    script = Path(__file__).resolve().parents[5] / "scripts" / "verify_binder.py"
    files["verify_binder.py"] = script.read_bytes() if script.is_file() else _verifier_bytes()
    manifest_files: dict[str, JsonValue] = {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }
    key_id, key = signing_material(store)
    manifest_body: dict[str, JsonValue] = {
        "created_at": utcnow().isoformat(),
        "files": manifest_files,
        "signer": key_id,
        "title": str(row.get("title") or ""),
    }
    signature, digest = sign_manifest(key, manifest_body)
    manifest_body["manifest_sha256"] = digest
    manifest_body["signature"] = signature
    manifest_body["public_key_pem"] = public_pem(key)
    files["manifest.json"] = canonical_json(manifest_body)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _count(selection: dict[str, object]) -> int:
    total = 0
    for value in selection.values():
        if isinstance(value, list):
            total += len(value)
    return total


def _limit() -> int:
    raw = os.environ.get("AR_BINDER_MAX_ITEMS", "").strip()
    return int(raw) if raw else _CAP


def _signed(store: Any, item_id: object) -> bool:
    if not isinstance(item_id, uuid.UUID):
        return False
    item = store.review_items.get(item_id)
    return isinstance(item, dict) and item.get("status") == "signed"


def _guest_binder(store: Any, actor: Actor, binder_id: object) -> bool:
    from ar_domain.identity.guests import guest_allows  # noqa: PLC0415

    return isinstance(binder_id, uuid.UUID) and guest_allows(store, actor, "binder", binder_id)


def _pdf(title: str) -> bytes:
    safe = "".join(char if 32 <= ord(char) < 127 else " " for char in title)[:80]
    stream = f"BT /F1 18 Tf 72 720 Td ({safe}) Tj ET".encode()
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        + f"4 0 obj<< /Length {len(stream)} >>stream\n".encode()
        + stream
        + b"\nendstream endobj\n"
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n%%EOF\n"
    )


def _xlsx(selection: dict[str, object]) -> bytes:
    rows = ["record_class,record_id"]
    for key, value in selection.items():
        if isinstance(value, list):
            rows.extend(f"{key},{item}" for item in value)
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(
            f'<row r="{index}"><c t="inlineStr"><is><t>{_xml(line)}</t></is></c></row>'
            for index, line in enumerate(rows, start=1)
        )
        + "</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="records" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _verifier_bytes() -> bytes:
    return b"print('verify_binder')\n"


def review_gate(
    store: Any, routine: dict[str, object], target: dict[str, object]
) -> dict[str, object] | None:
    """Hold a delivery until its review item is signed. None means send now."""
    if target.get("review_before_send") is not True:
        return None
    tenant_id = routine.get("tenant_id")
    marker = f"delivery-{routine.get('id')}-{target.get('type')}"
    found = None
    for row in bucket(store, "binders").values():
        if row.get("delivery_marker") == marker:
            found = row
            break
    if found is None:
        binder_id = new_id()
        item_id = new_id()
        found = {
            "id": binder_id,
            "tenant_id": tenant_id,
            "title": f"Delivery {target.get('type')}",
            "status": "pending_review",
            "selection": {},
            "require_review": True,
            "review_item_id": item_id,
            "delivery_marker": marker,
            "created_by": routine.get("owner_user_id"),
            "created_at": utcnow(),
        }
        bucket(store, "binders")[binder_id] = found
        store.review_items[item_id] = {
            "id": item_id,
            "tenant_id": tenant_id,
            "subject_type": "binder",
            "subject_id": binder_id,
            "status": "pending",
        }
    item = store.review_items.get(found.get("review_item_id"))
    if isinstance(item, dict) and item.get("status") == "signed":
        return None
    return {
        "target": str(target.get("type") or ""),
        "result": "waiting",
        "review_item_id": str(found.get("review_item_id")),
    }
