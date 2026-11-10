"""Records pack. Core does not import this package.

Mount it to serve the desk, and enable it per tenant. Unsigned loads are refused
when signature checks are required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from records_pack.tools import PACK_PERMISSIONS, dispatch_records, register_tools

if TYPE_CHECKING:
    import uuid
    from typing import Any

__all__ = ["PACK_PERMISSIONS", "enable", "mount"]


def mount(app: Any) -> None:
    """Attach routes, the tool endpoint and the publish and review hooks."""
    from ar_api.middleware.stack import allow_guest_get  # noqa: PLC0415
    from ar_api.plugins import include_pack  # noqa: PLC0415
    from ar_domain.packs.hooks import register_publish_hook, register_review_hook  # noqa: PLC0415
    from ar_domain.tools.handlers import register_endpoint  # noqa: PLC0415
    from records_pack.router import router  # noqa: PLC0415

    include_pack(app, "records", router)
    allow_guest_get("api", "v1", "binders")
    register_endpoint("builtin://records", dispatch_records)
    register_publish_hook(_on_publish)
    register_review_hook(_on_review)


def enable(store: Any, tenant_id: uuid.UUID, *, owner: uuid.UUID | None = None) -> None:
    """Mark the pack enabled for one tenant and register its tools and permissions."""
    from ar_common.time import utcnow  # noqa: PLC0415
    from ar_domain.packs.registry import (  # noqa: PLC0415
        register_pack_audit_actions,
        register_pack_permissions,
    )
    from ar_domain.records.memory import bucket  # noqa: PLC0415

    register_pack_permissions(store, "records", list(PACK_PERMISSIONS))
    register_pack_audit_actions(
        store,
        "records",
        ["evidence.captured", "evidence.verified", "binder.created"],
    )
    bucket(store, "pack_flags")[(str(tenant_id), "records")] = {
        "tenant_id": tenant_id,
        "pack_id": "records",
        "enabled": True,
        "nav": [{"href": "/packs/records", "label": "Records", "permission": "evidence:read"}],
        "updated_at": utcnow(),
    }
    register_tools(store, tenant_id=tenant_id, owner=owner)


def _on_publish(store: Any, actor: Any, agent: Any, version: Any) -> None:
    if not _enabled(store, getattr(actor, "tenant_id", None)):
        return
    from records_pack.cards import GovernanceBook  # noqa: PLC0415

    GovernanceBook(store).publish_card(actor, agent, version)


def _on_review(store: Any, routine: Any, target: Any) -> Any:
    tenant_id = routine.get("tenant_id") if isinstance(routine, dict) else None
    if not _enabled(store, tenant_id):
        return None
    from records_pack.binders import review_gate  # noqa: PLC0415

    return review_gate(store, routine, target)


def _enabled(store: Any, tenant_id: object) -> bool:
    from ar_domain.records.memory import bucket  # noqa: PLC0415

    for flag in bucket(store, "pack_flags").values():
        if flag.get("pack_id") != "records" or not flag.get("enabled"):
            continue
        if tenant_id is None or flag.get("tenant_id") == tenant_id:
            return True
        if str(flag.get("tenant_id")) == str(tenant_id):
            return True
    return False
