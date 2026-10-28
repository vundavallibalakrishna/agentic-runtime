"""Prepared-by-client requests. A guest sees only the ids in the grant."""

from __future__ import annotations

import html
import io
import re
import zipfile
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.memory import bucket
from ar_domain.records.watermark import watermark
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import bind, open_review, signed_for
from ar_pack_grc.values import as_uuid, required_text, when

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

AUDITOR_PORTAL = "auditor"
_STATUSES = frozenset({"open", "responded", "provided", "accepted"})


def register_portal(store: Any) -> None:
    """Auditor guest portal. Core already allows `/api/v1/ext/`."""
    bucket(store, "pack_portals")[AUDITOR_PORTAL] = {"pack_id": "grc", "portal": AUDITOR_PORTAL}


def list_requests(store: Any, actor: Actor) -> dict[str, Any]:
    granted = _granted(store, actor) if actor.kind == "guest" else None
    items = []
    for row in bucket_rows(store, "grc_pbc_requests").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if not _visible(actor, row, granted):
            continue
        items.append(present(row))
    return page(items)


def create_request(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.audit_portal:manage")
    body = snake_body(payload)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "title": required_text(body.get("title"), "title"),
        "control_id": as_uuid(body.get("control_id"), required=False),
        "owner_user_id": as_uuid(body.get("owner_user_id")),
        "status": "open",
        "response_md": "",
        "content_hash": None,
        "due_at": when(body.get("due_at")),
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    bucket_rows(store, "grc_pbc_requests")[item_id] = row
    record(store, actor, "grc.pbc.updated", item_id, {"status": "open"})
    return present(row)


def update_request(
    store: Any, actor: Actor, request_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    row = one(store, "grc_pbc_requests", actor, request_id)
    granted = _granted(store, actor) if actor.kind == "guest" else None
    if not _visible(actor, row, granted):
        raise NotFoundError()
    body = snake_body(payload)
    if actor.kind == "guest":
        return _guest_accept(store, actor, row, body)
    require(actor, "grc.audit_portal:manage")
    if body.get("response_md") is not None:
        _respond(store, actor, row, str(body.get("response_md") or ""))
    status = str(body.get("status") or "")
    if status:
        _status(store, actor, row, status)
    row["updated_at"] = utcnow()
    record(store, actor, "grc.pbc.updated", row["id"], {"status": row.get("status")})
    return present(row)


def import_list(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.audit_portal:manage")
    body = snake_body(payload)
    file_id = as_uuid(body.get("file_id"))
    data = _file_bytes(store, actor, file_id)
    rows = _sheet(data)
    if not rows:
        raise ValidationFailedError("workbook is empty")
    header = [_header(cell) for cell in rows[0]]
    created = []
    for cells in rows[1:]:
        mapped = {header[index]: cells[index] for index in range(min(len(header), len(cells)))}
        title = str(mapped.get("title") or "").strip()
        if not title:
            continue
        owner = mapped.get("owner_user_id") or actor.user_id
        created.append(
            create_request(
                store,
                actor,
                {
                    "title": title,
                    "owner_user_id": owner,
                    "control_id": mapped.get("control_id") or None,
                    "due_at": mapped.get("due_at") or None,
                },
            )
        )
    return {"items": created, "count": len(created)}


def response_pdf(store: Any, actor: Actor, request_id: uuid.UUID) -> bytes:
    row = one(store, "grc_pbc_requests", actor, request_id)
    granted = _granted(store, actor) if actor.kind == "guest" else None
    if not _visible(actor, row, granted):
        raise NotFoundError()
    text = str(row.get("response_md") or "").strip()
    if not text:
        raise NotFoundError()
    pdf = _pdf(str(row.get("title") or "PBC"), text)
    if actor.kind != "guest":
        return pdf
    label = f"{actor.display_name} {actor.tenant_id}"
    return watermark(pdf, "application/pdf", label)


def _guest_accept(
    store: Any, actor: Actor, row: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any]:
    if str(body.get("status") or "") != "accepted":
        raise ForbiddenError()
    if row.get("status") != "provided":
        raise ConflictError("review_required")
    row["status"] = "accepted"
    row["updated_at"] = utcnow()
    record(store, actor, "grc.pbc.updated", row["id"], {"status": "accepted"})
    return present(row)


def _respond(store: Any, actor: Actor, row: dict[str, Any], text: str) -> None:
    digest = bind(store, row["id"], text)
    open_review(
        store,
        actor,
        slug="grc-pbc",
        subject_id=row["id"],
        content=text,
        statement=f"I reviewed the PBC response for {row.get('title')}.",
    )
    row["response_md"] = text
    row["content_hash"] = digest
    if row.get("status") == "open":
        row["status"] = "responded"


def _status(store: Any, actor: Actor, row: dict[str, Any], status: str) -> None:
    del actor
    if status not in _STATUSES:
        raise ValidationFailedError("status is invalid")
    if status == "provided":
        digest = str(row.get("content_hash") or "")
        if signed_for(store, row["id"], digest) is None:
            raise ConflictError("review_required")
    row["status"] = status


def _visible(actor: Actor, row: dict[str, Any], granted: set[str] | None) -> bool:
    if actor.kind == "guest":
        return granted is not None and str(row.get("id")) in granted
    if actor.has("grc.audit_portal:manage"):
        return True
    return str(row.get("owner_user_id") or "") == str(actor.user_id)


def _granted(store: Any, actor: Actor) -> set[str]:
    found: set[str] = set()
    for grant in bucket(store, "guest_grants").values():
        if not isinstance(grant, dict):
            continue
        if str(grant.get("guest_id") or "") != str(actor.user_id):
            continue
        if str(grant.get("portal") or "") not in {AUDITOR_PORTAL, "records"}:
            continue
        scope = grant.get("scope")
        raw = scope.get("pack_record_ids") if isinstance(scope, dict) else []
        if isinstance(raw, list):
            found.update(str(item) for item in raw)
    return found


def _file_bytes(store: Any, actor: Actor, file_id: uuid.UUID | None) -> bytes:
    if file_id is None:
        raise NotFoundError()
    row = store.files.get(file_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()
    data = store.blobs.get(file_id)
    if not isinstance(data, bytes):
        raise NotFoundError()
    return data


def _header(cell: str) -> str:
    cleaned = cell.strip()
    return next(iter(snake_body({cleaned: cleaned})))


def _sheet(data: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationFailedError("workbook is invalid") from exc
    with archive:
        sheets = [name for name in archive.namelist() if name.startswith("xl/worksheets/sheet")]
        if not sheets:
            raise ValidationFailedError("workbook has no sheet")
        xml = archive.read(sheets[0]).decode("utf-8", errors="replace")
    rows: list[list[str]] = []
    for row in re.findall(r"<row\b[^>]*>.*?</row>", xml, flags=re.DOTALL):
        cells = re.findall(r"<t[^>]*>(.*?)</t>", row, flags=re.DOTALL)
        if not cells:
            cells = re.findall(r"<v[^>]*>(.*?)</v>", row)
        values = [html.unescape(cell).strip() for cell in cells]
        if any(values):
            rows.append(values)
    return rows


def _pdf(title: str, body: str) -> bytes:
    safe = "".join(char if 32 <= ord(char) < 127 else " " for char in f"{title} {body}")[:80]
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode()
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
