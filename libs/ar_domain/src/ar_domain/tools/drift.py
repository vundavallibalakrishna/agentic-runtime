"""Manifest drift. Spec: docs/03-specs/08-tool-registry-mcp.md §8."""

from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.tools.logic import manifest_hash

if TYPE_CHECKING:
    from typing import Any


def check_drift(store: Any) -> list[dict[str, object]]:
    """Re-discover approved remote servers. A change never becomes the new manifest."""
    changed: list[dict[str, object]] = []
    for server in list(store.tool_servers.values()):
        if server.get("kind") != "remote_mcp" or server.get("status") != "approved":
            continue
        version_id = server.get("current_version_id")
        version = store.tool_server_versions.get(version_id)
        if not isinstance(version, dict):
            continue
        upstream = version.get("upstream_manifest")
        if not isinstance(upstream, dict):
            continue
        digest = manifest_hash(upstream)
        if digest == version.get("manifest_hash"):
            continue
        server["status"] = "pending_review"
        server["updated_at"] = utcnow()
        version["review_notes"] = f"manifest_drift {digest}"
        version["upstream_hash"] = digest
        store.domain_events.append(
            {
                "topic": "tool_server.review_requested",
                "payload": {
                    "tool_server_id": str(server["id"]),
                    "tool_server_version_id": str(version["id"]),
                    "reason": "manifest_drift",
                },
                "at": utcnow().isoformat(),
            }
        )
        store.audit_log.append(
            {
                "action": "tool_server.review_requested",
                "target_id": str(server["id"]),
                "detail": {"reason": "manifest_drift"},
                "at": utcnow().isoformat(),
            }
        )
        changed.append({"server_id": str(server["id"]), "manifest_hash": digest})
    return changed
