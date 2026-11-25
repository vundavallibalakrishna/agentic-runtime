"""A finished chart thread for the demo tenant, so the computer panel is not empty.

The conversation, its two messages, the picture and the computer are written as rows: no
model ran and no computer drew the chart. That is why this lives in the test library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.sandboxkit import png_chart
from ar_common.time import utcnow
from ar_domain.demo_ids import demo_id
from ar_domain.files.logic import object_key
from ar_domain.files.objects import keep_bytes
from ar_domain.sandboxes.runtime import workspace_root

if TYPE_CHECKING:
    import uuid


def seed_chart(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """A finished chart thread so the computer panel is not empty."""
    conversation_id = demo_id("showcase-revenue")
    if conversation_id in store.conversations:
        return
    agent = next(
        (
            row
            for row in store.agents.values()
            if row.get("tenant_id") == tenant_id and row.get("slug") == "revenue-analyst"
        ),
        None,
    )
    if agent is None:
        return
    now = utcnow()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "title": "Revenue by month",
        "status": "active",
        "pinned": False,
        "is_preview": False,
        "agent_version_id": agent.get("published_version_id"),
        "active_run_id": None,
        "plan": [],
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    question = "Analyse the attached CSV and chart revenue by month"
    answer = "wrote revenue-by-month.png"
    _message(store, tenant_id, conversation_id, user_id, role="user", text=question, now=now)
    _message(store, tenant_id, conversation_id, user_id, role="assistant", text=answer, now=now)
    png = png_chart([12000, 15000, 18000, 14000, 21000, 19000])
    file_id = demo_id("showcase-revenue-png")
    file_row = {
        "id": file_id,
        "tenant_id": tenant_id,
        "owner_user_id": user_id,
        "conversation_id": conversation_id,
        "kind": "artifact",
        "name": "revenue-by-month.png",
        "mime_type": "image/png",
        "size_bytes": len(png),
        "object_key": object_key(
            str(tenant_id), "artifact", f"{now:%Y}", f"{now:%m}", str(file_id)
        ),
        "status": "ready",
        "scan_status": "skipped",
        "preview": {},
        "created_at": now,
        "deleted_at": None,
    }
    store.files[file_id] = file_row
    # The chart bytes go to the object store, not process memory, so the preview
    # survives the request and any replica can read it.
    keep_bytes(store, file_row, png)
    sandbox_id = demo_id("showcase-revenue-sandbox")
    store.sandboxes[sandbox_id] = {
        "id": sandbox_id,
        "tenant_id": tenant_id,
        "template_id": demo_id("sandbox-template-python-data"),
        "template_slug": "python-data",
        "scope": "conversation",
        "scope_key": f"conv:{conversation_id}",
        "conversation_id": conversation_id,
        "agent_id": agent["id"],
        "user_id": user_id,
        "status": "ready",
        "driver": "docker",
        "driver_ref": f"local:{sandbox_id}",
        "created_at": now,
        "updated_at": now,
        "last_active_at": now,
    }
    root = workspace_root(sandbox_id)
    (root / "workspace" / "outputs").mkdir(parents=True, exist_ok=True)
    (root / "workspace" / "outputs" / "revenue-by-month.png").write_bytes(png)


def _message(
    store: Any,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    role: str,
    text: str,
    now: object,
) -> None:
    message_id = new_id()
    store.messages[message_id] = {
        "id": message_id,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "parent_message_id": None,
        "role": role,
        "content": [{"type": "text", "text": text}],
        "text": text,
        "status": "completed",
        "is_active_branch": True,
        "attachments": [],
        "created_at": now,
        "author_user_id": user_id if role == "user" else None,
    }
