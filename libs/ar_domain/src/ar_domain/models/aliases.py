"""The aliases the product itself asks for. Spec: docs/03-specs/04-model-gateway.md.

An agent, knowledge and memory name a model by alias, never by model id. These are the
alias names the product calls today and the kind of model each needs. A tenant sets each
one on the Models screen; none is set for it. A tenant may add aliases of its own beside
them. An agent definition also names ``fast``; nothing is sent to it yet, so it is not
listed here until something is.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True, slots=True)
class StandardAlias:
    """An alias name the product uses, and whether work stops without it."""

    alias: str
    kind: str
    required: bool
    # What the model behind the alias must be able to do, beyond being of the kind.
    capability: str | None = None


STANDARD_ALIASES: tuple[StandardAlias, ...] = (
    # Every agent answers with it.
    StandardAlias("reasoning", "chat", required=True),
    # The image tool reads pictures with it. Its model is marked as able to read images.
    StandardAlias("vision", "chat", required=False, capability="vision"),
    # Knowledge and memory refuse to store anything without it.
    StandardAlias("embed", "embedding", required=True),
    # Scores search results. Without it they are returned unscored.
    StandardAlias("rerank", "rerank", required=False),
)

# What a chat alias sends when the caller does not say. It is a setting of the alias.
CHAT_DEFAULT_PARAMS: dict[str, object] = {"temperature": 0.2}


# What a tenant may say a model can do. ``vision`` lets the image tool use it.
CAPABILITIES = frozenset({"streaming", "tools", "vision"})


def default_params(kind: str) -> dict[str, object]:
    """The parameters a new alias of ``kind`` starts with."""
    return dict(CHAT_DEFAULT_PARAMS) if kind == "chat" else {}


def standard_aliases(store: Any, tenant_id: uuid.UUID) -> list[dict[str, object]]:
    """Each alias the product uses, with the model the tenant pointed it at, if any.

    A tenant's own alias wins over one that belongs to no tenant.
    """
    found: list[dict[str, object]] = []
    for item in STANDARD_ALIASES:
        row = _resolve(store, tenant_id, item.alias)
        model = None
        if row is not None:
            model = store.models.get(_as_uuid(row.get("primary_model_id")))
        found.append(
            {
                "alias": item.alias,
                "kind": item.kind,
                "required": item.required,
                "capability": item.capability,
                "set": isinstance(model, dict),
                "alias_id": str(row["id"]) if row is not None else None,
                "platform": bool(row is not None and row.get("tenant_id") is None),
                "model_id": str(model["id"]) if isinstance(model, dict) else None,
                "model_name": str(model.get("name") or "") if isinstance(model, dict) else None,
            }
        )
    return found


def _resolve(store: Any, tenant_id: uuid.UUID, alias: str) -> dict[str, object] | None:
    own: dict[str, object] | None = None
    shared: dict[str, object] | None = None
    for row in store.aliases.values():
        if row.get("alias") != alias or str(row.get("status") or "active") != "active":
            continue
        if row.get("tenant_id") == tenant_id:
            own = own or row
        elif row.get("tenant_id") is None:
            shared = shared or row
    return own or shared


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
