"""Data-principal export. Spec: docs/06-security/data-protection.md."""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import audit

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def export_user(store: Any, actor: Actor) -> dict[str, object]:
    """Build a ZIP of the caller's own rows and record that it is ready."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "profile.json",
            f'{{"userId":"{actor.user_id}","email":"{actor.display_name}"}}\n',
        )
        for name, source in (
            ("conversations", store.conversations),
            ("files", store.files),
            ("memory", store.memory_facts),
        ):
            lines = [
                str(row.get("id"))
                for row in source.values()
                if isinstance(row, dict)
                and row.get("tenant_id") == actor.tenant_id
                and row.get("user_id") == actor.user_id
            ]
            archive.writestr(f"{name}.txt", "\n".join(lines))
    export_id = new_id()
    store.notifications.append(
        {
            "id": export_id,
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "kind": "export_ready",
            "created_at": utcnow().isoformat(),
        }
    )
    store.blobs[export_id] = buffer.getvalue()
    notice = getattr(store, "user_settings", {})
    if isinstance(notice, dict):
        current = notice.get(actor.user_id)
        if not isinstance(current, dict):
            current = {}
            notice[actor.user_id] = current
        attributes = current.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}
            current["attributes"] = attributes
        attributes["notice_version"] = attributes.get("notice_version") or "2026-10"
    audit(store, actor, "user.data_exported", "user", actor.user_id, {"export_id": str(export_id)})
    return {"export_id": str(export_id), "status": "ready"}
