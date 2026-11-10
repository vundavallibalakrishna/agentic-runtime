"""Portable instructions for filling a questionnaire workbook."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.demo_ids import demo_id

if TYPE_CHECKING:
    from typing import Any

SLUG = "questionnaire-writeback"
INSTRUCTIONS = (
    "Fill a questionnaire spreadsheet and write the answers back into an xlsx "
    "the user can download.\n"
    "1. Inspect the workbook with general.inspect_table so you know the sheet "
    "and the column names.\n"
    "2. Find support in the document library, or use passages the user already "
    "retrieved. Do not invent an answer that has no passage.\n"
    "3. Call documents.fill_questionnaire with the workspace path. Pass answers "
    "as id, question, answer, notes and citation, or pass documentId so a row "
    "can be grounded in that document.\n"
    "4. A row with no support stays blank and is marked unanswered. Say which "
    "rows were unanswered.\n"
    "5. Give the user the downloaded file. Do not paste the whole sheet into the chat.\n"
)


def ensure_questionnaire_skill(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Publish the skill once per process store."""
    from ar_common.time import utcnow  # noqa: PLC0415
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415
    from ar_domain.skills.book import SkillBook  # noqa: PLC0415
    from ar_domain.skills.logic import file_sha256  # noqa: PLC0415

    rows = getattr(store, "skills", None)
    if isinstance(rows, dict) and any(
        isinstance(row, dict) and row.get("slug") == SLUG for row in rows.values()
    ):
        return
    if not isinstance(getattr(store, "files", None), dict):
        store.files = {}
    if not isinstance(getattr(store, "blobs", None), dict):
        store.blobs = {}
    file_id = demo_id("skill-questionnaire-asset")
    blob = INSTRUCTIONS.encode()
    now = utcnow()
    store.files.setdefault(
        file_id,
        {
            "id": file_id,
            "tenant_id": tenant_id,
            "owner_user_id": user_id,
            "conversation_id": None,
            "run_id": None,
            "kind": "upload",
            "name": "questionnaire.md",
            "mime_type": "text/markdown",
            "size_bytes": len(blob),
            "sha256": file_sha256(blob),
            "object_key": f"skills/{file_id}",
            "classification": "internal",
            "status": "ready",
            "scan_status": "skipped",
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        },
    )
    store.blobs.setdefault(file_id, blob)
    actor = Actor(tenant_id, user_id, PERMISSION_KEYS, display_name="Admin")
    book = SkillBook(store)
    created = book.create(
        actor,
        {
            "slug": SLUG,
            "name": "Questionnaire write-back",
            "description": "Fill a SIG or CAIQ style workbook from known answers or a document.",
            "visibility": "tenant",
            "instructions_md": INSTRUCTIONS,
            "required_tools": [
                "general.inspect_table",
                "documents.search",
                "documents.fill_questionnaire",
            ],
            "assets": [{"path": "questionnaire.md", "file_id": file_id}],
        },
    )
    book.publish(actor, uuid.UUID(str(created["id"])), change_note="Questionnaire write-back")
