"""Pack extension registration. Core does not import a pack package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import ArError, ErrorCode, ForbiddenError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.identity.service import assert_step_up
from ar_domain.records.holds import is_held
from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_MIGRATORS: dict[str, Any] = {}


def register_migrator(schema: str, migrator: Any) -> None:
    """Testing kit and operators register a schema migrator by name."""
    _MIGRATORS[schema] = migrator


def register_pack_permissions(store: Any, pack_id: str, keys: list[str]) -> None:
    catalogue = bucket(store, "pack_permissions")
    catalogue[pack_id] = {"pack_id": pack_id, "keys": list(keys)}


def register_pack_audit_actions(store: Any, pack_id: str, actions: list[str]) -> None:
    catalogue = bucket(store, "pack_actions")
    catalogue[pack_id] = {"pack_id": pack_id, "actions": list(actions)}


def apply_extension(store: Any, actor: Actor, parsed: Any) -> None:
    """Run the pack migration, then record the registration and tenant flag."""
    extension = parsed.spec.extension
    schema = str(extension.schema_name or "")
    if schema:
        migrator = _MIGRATORS.get(schema)
        if migrator is None:
            raise ArError(ErrorCode.EXTENSION_UNAVAILABLE, "pack schema is not in this image")
        migrator(store, actor, schema)
    register_pack_permissions(store, parsed.metadata.id, list(extension.permissions))
    register_pack_audit_actions(store, parsed.metadata.id, list(extension.audit_actions))
    registration_id = new_id()
    bucket(store, "pack_registrations")[registration_id] = {
        "id": registration_id,
        "tenant_id": actor.tenant_id,
        "pack_id": parsed.metadata.id,
        "version": parsed.metadata.version,
        "manifest": {"ui": dict(extension.ui), "schema": schema},
        "created_at": utcnow(),
    }
    bucket(store, "pack_flags")[(str(actor.tenant_id), parsed.metadata.id)] = {
        "tenant_id": actor.tenant_id,
        "pack_id": parsed.metadata.id,
        "enabled": True,
        "settings": dict(extension.config_schema),
        "nav": _nav(extension.ui),
        "updated_at": utcnow(),
    }


def drop_pack_schema(store: Any, actor: Actor, pack_id: str) -> None:
    """Refuse without step-up, and refuse when a hold covers a pack row."""
    assert_step_up(actor.step_up_at, now=utcnow(), ttl_s=600, required=True)
    for row in bucket(store, "pack_rows").values():
        if row.get("pack_id") == pack_id and is_held(store, "pack_record", row.get("id")):
            raise ArError(ErrorCode.HOLD_ACTIVE, "hold_active")
    flag = bucket(store, "pack_flags").get((str(actor.tenant_id), pack_id))
    if isinstance(flag, dict):
        flag["enabled"] = False
        flag["schema_dropped"] = True


def tenant_packs(store: Any, actor: Actor) -> list[dict[str, object]]:
    rows = []
    for flag in bucket(store, "pack_flags").values():
        if flag.get("tenant_id") != actor.tenant_id:
            continue
        item: dict[str, object] = {
            "pack_id": flag.get("pack_id"),
            "version": _version(store, actor, str(flag.get("pack_id"))),
            "enabled": bool(flag.get("enabled")),
        }
        if flag.get("enabled") and _can_see_nav(actor, flag):
            item["nav"] = flag.get("nav") or []
        rows.append(item)
    return rows


def set_enabled(store: Any, actor: Actor, pack_id: str, *, enabled: bool) -> dict[str, object]:
    if not actor.has("packs:manage"):
        raise ForbiddenError("missing permission packs:manage")
    flag = bucket(store, "pack_flags").get((str(actor.tenant_id), pack_id))
    if not isinstance(flag, dict):
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError()
    flag["enabled"] = enabled
    action = "tenant_pack.enabled" if enabled else "tenant_pack.disabled"
    from ar_domain.records.access import audit  # noqa: PLC0415

    audit(store, actor, action, "tenant_pack", pack_id, {})
    return {"pack_id": pack_id, "enabled": enabled}


def _nav(ui: dict[str, object]) -> list[object]:
    nav = ui.get("nav")
    return list(nav) if isinstance(nav, list) else []


def _version(store: Any, actor: Actor, pack_id: str) -> str:
    for row in bucket(store, "pack_registrations").values():
        if row.get("tenant_id") == actor.tenant_id and row.get("pack_id") == pack_id:
            return str(row.get("version") or "")
    return ""


def _can_see_nav(actor: Actor, flag: dict[str, object]) -> bool:
    nav = flag.get("nav")
    if not isinstance(nav, list) or not nav:
        return True
    first = nav[0]
    if isinstance(first, dict) and isinstance(first.get("permission"), str):
        return actor.has(str(first["permission"]))
    return True
