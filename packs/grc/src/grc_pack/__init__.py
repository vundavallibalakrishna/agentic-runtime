"""GRC pack. Core does not import this package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grc_pack.tools import PACK_PERMISSIONS, dispatch_grc, register_tools

if TYPE_CHECKING:
    import uuid

__all__ = ["PACK_PERMISSIONS", "enable", "mount"]


def mount(app: Any) -> None:
    """Attach the routes and the tool endpoint."""
    from ar_api.plugins import include_pack  # noqa: PLC0415
    from ar_domain.tools.handlers import register_endpoint  # noqa: PLC0415
    from grc_pack.router import router  # noqa: PLC0415

    include_pack(app, "grc", router)
    register_endpoint("builtin://grc", dispatch_grc)


def enable(store: Any, tenant_id: uuid.UUID, *, owner: uuid.UUID | None = None) -> None:
    """Mark the pack enabled and register its tools."""
    from ar_common.time import utcnow  # noqa: PLC0415
    from ar_domain.packs.registry import (  # noqa: PLC0415
        register_pack_audit_actions,
        register_pack_permissions,
    )
    from ar_domain.records.memory import bucket  # noqa: PLC0415

    register_pack_permissions(store, "grc", list(PACK_PERMISSIONS))
    register_pack_audit_actions(
        store,
        "grc",
        ["grc.catalogue.imported", "grc.evidence.linked", "grc.risk.added", "grc.finding.added"],
    )
    bucket(store, "pack_flags")[(str(tenant_id), "grc")] = {
        "tenant_id": tenant_id,
        "pack_id": "grc",
        "enabled": True,
        "nav": [{"href": "/packs/grc", "label": "GRC", "permission": "grc.catalogues:manage"}],
        "updated_at": utcnow(),
    }
    register_tools(store, tenant_id=tenant_id, owner=owner)
