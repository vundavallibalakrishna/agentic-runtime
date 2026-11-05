"""image.ask. One question about a screenshot, chart, UI or diagram."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ArError

if TYPE_CHECKING:
    from typing import Any
from ar_domain.documents.vision import VisionError, ask_image
from ar_domain.tools.documents import _actor, _error, _ok, _source_bytes


def dispatch_image(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Run one image tool. Unknown names are errors."""
    if name != "ask":
        return _error("unknown_tool", f"unknown tool {name}")
    actor = _actor(arguments)
    if actor is None:
        return _error("validation_failed", "The image tool needs a tenant.")
    question = str(arguments.get("question") or "").strip()
    if not question:
        return _error("validation_failed", "question is required.")
    try:
        data, filename, media, _source, _ref = _source_bytes(store, arguments)
    except ArError as exc:
        return _error(exc.code.value, exc.detail)
    alias = _vision_alias(store, arguments)
    try:
        answer = ask_image(
            store,
            actor.tenant_id,
            alias=alias,
            question=question,
            data=data,
            media_type=media or filename,
        )
    except VisionError as exc:
        return _error(exc.code, exc.message)
    return _ok(answer, {"kind": "image_ask", "alias": alias or "vision"})


def _vision_alias(store: Any, arguments: dict[str, object]) -> str:
    named = arguments.get("visionAlias") or arguments.get("vision_alias")
    if isinstance(named, str) and named.strip():
        return named.strip()
    version_id = arguments.get("_agent_version_id")
    versions = getattr(store, "versions", None)
    version = (
        versions.get(version_id)
        if isinstance(versions, dict) and isinstance(version_id, uuid.UUID)
        else None
    )
    definition = version.get("definition") if isinstance(version, dict) else None
    model = definition.get("model") if isinstance(definition, dict) else None
    if isinstance(model, dict):
        alias = model.get("vision_alias") or model.get("visionAlias")
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
    return "vision"
