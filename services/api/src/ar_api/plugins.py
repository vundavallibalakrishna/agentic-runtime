"""Pack HTTP mounts. Core discovers packs; it does not import them."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI


def include_pack(app: FastAPI, pack_id: str, router: APIRouter) -> None:
    """Attach a pack router once. The router carries its own `/api/v1/ext` prefix."""
    mounted = getattr(app.state, "mounted_packs", None)
    if not isinstance(mounted, set):
        mounted = set()
        app.state.mounted_packs = mounted
    if pack_id in mounted:
        return
    app.include_router(router)
    mounted.add(pack_id)


def attach_packs(app: FastAPI) -> None:
    """Load installed pack entry points. A missing pack leaves the API unchanged."""
    for item in entry_points(group="agentic_runtime.packs"):
        hook = item.load()
        hook(app)
