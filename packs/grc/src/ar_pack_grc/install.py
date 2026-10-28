"""Install the GRC content pack and seed the catalogues that ship with it."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import orjson
import yaml

from ar_common.ids import new_id
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.packs.registry import register_migrator
from ar_domain.records.memory import bucket
from ar_domain.tools.seed_tools import register_builtin_server
from ar_pack_grc.access import owned
from ar_pack_grc.ccm import seed_monitoring
from ar_pack_grc.connectors.registry import install_servers, register_servers
from ar_pack_grc.mappings import seed_common
from ar_pack_grc.mcp_server import register, tool_definitions
from ar_pack_grc.oscal import import_catalog, load_json

if TYPE_CHECKING:
    from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CATALOGUES = ROOT / "catalogues"
MANIFEST = ROOT / "manifest.yaml"
_MONITOR_PERMISSIONS = frozenset(
    {
        "grc.controls:manage",
        "grc.controls:read",
        "grc.tests:read",
        "grc.tests:run",
        "grc.evidence:link",
        "grc.findings:manage",
        "grc.findings:read",
        "evidence:read",
        "evidence:capture",
        "routines:create",
    }
)


def bootstrap(app: Any) -> None:
    """Mount routes and, outside tests, install the pack for the dev tenant."""
    from ar_api.plugins import include_pack  # noqa: PLC0415
    from ar_pack_grc.router import router  # noqa: PLC0415

    include_pack(app, "grc", router)
    register()
    register_servers()
    register_migrator("grc", _migrate)
    store = getattr(getattr(app, "state", None), "chat", None)
    if store is not None and _dev_install():
        install_dev(store)


def install_dev(store: Any) -> None:
    binding = getattr(store, "dev_binding", None)
    if binding is not None:
        tenant_id = binding.tenant_id
        user_id = binding.users.get("admin@dev.local", demo_id("admin"))
    else:
        tenant_id = demo_id("tenant")
        user_id = demo_id("admin")
    actor = Actor(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=PERMISSION_KEYS | _MONITOR_PERMISSIONS,
        roles=frozenset({"tenant_admin"}),
    )
    install_for(store, actor)
    seed_monitoring(store, actor)


def install_for(store: Any, actor: Actor) -> dict[str, object]:
    register()
    register_migrator("grc", _migrate)
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("GRC manifest is not an object")
    installed = PackService(store).install(actor, manifest, signature=None, key_id=None)
    seed_catalogues(store, actor)
    register_builtin_server(
        store,
        tenant_id=None,
        owner=actor.user_id,
        slug="grc",
        name="GRC",
        description="Read controls, mappings, vendors, policies and obligations.",
        endpoint="builtin://grc",
        tools=tool_definitions(),
    )
    _qualify(store)
    install_servers(store, actor.user_id)
    return installed


def _qualify(store: Any) -> None:
    """Keep the spec names on qualified_name. The name column stays dot-free."""
    from ar_pack_grc.mcp_server import _STORED  # noqa: PLC0415

    for row in store.tool_defs.values():
        stored = str(row.get("name") or "")
        if stored in _STORED:
            row["qualified_name"] = f"grc.{_STORED[stored]}"
    for row in store.tool_versions.values():
        stored = str(row.get("name") or "")
        if stored in _STORED:
            row["qualified_name"] = f"grc.{_STORED[stored]}"


def seed_catalogues(store: Any, actor: Actor) -> None:
    if any(row.get("key") == "nist-csf" for row in owned(store, "grc_frameworks", actor)):
        return
    for name in ("nist-csf-2.0.json", "nist-800-53.json", "csa-ccm.json"):
        import_catalog(
            store,
            actor,
            load_json((CATALOGUES / name).read_bytes()),
            pack_owned=True,
        )
    skeletons = yaml.safe_load((CATALOGUES / "skeletons.yaml").read_text(encoding="utf-8"))
    for spec in skeletons.get("frameworks", []):
        import_catalog(store, actor, _skeleton_document(spec), pack_owned=True, licence="skeleton")
    obligations = yaml.safe_load((CATALOGUES / "obligations.yaml").read_text(encoding="utf-8"))
    for spec in obligations.get("obligations", []):
        item_id = new_id()
        bucket(store, "grc_obligations")[item_id] = {
            "id": item_id,
            "tenant_id": actor.tenant_id,
            "regulator": spec["regulator"],
            "citation": spec["citation"],
            "statement": spec["statement"],
            "status": "active",
            "owner_user_id": None,
        }
    for spec in obligations.get("feeds", []):
        item_id = new_id()
        bucket(store, "grc_regulator_feeds")[item_id] = {
            "id": item_id,
            "tenant_id": actor.tenant_id,
            "regulator": spec["regulator"],
            "url": spec["url"],
            "enabled": True,
        }
    common = yaml.safe_load((CATALOGUES / "common-controls.yaml").read_text(encoding="utf-8"))
    seed_common(store, actor, common)


def _skeleton_document(spec: dict[str, Any]) -> dict[str, Any]:
    controls = [
        {"id": str(item["key"]), "title": str(item["title"])} for item in spec.get("controls", [])
    ]
    groups = []
    for requirement in spec.get("requirements", []):
        prefix = str(requirement["key"])
        nested = [
            control
            for control in controls
            if str(control["id"]).startswith(prefix + ".") or str(control["id"]) == prefix
        ]
        groups.append({"id": prefix, "title": requirement["title"], "controls": nested})
    placed = {str(control["id"]) for group in groups for control in group["controls"]}
    loose = [control for control in controls if str(control["id"]) not in placed]
    return {
        "catalog": {
            "metadata": {
                "title": spec["name"],
                "version": str(spec["version"]),
                "props": [
                    {"name": "key", "value": spec["key"]},
                    {"name": "licence", "value": "skeleton"},
                ],
            },
            "groups": groups,
            "controls": loose,
        }
    }


def _migrate(store: Any, who: Any, schema: str) -> None:
    del who
    bucket(store, "pack_migrations")[schema] = {"schema": schema, "upgraded": True}


def _dev_install() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return os.environ.get("AR_ENV", "dev").strip().lower() in {"", "dev", "ci", "test"}


def catalogue_bytes(name: str) -> bytes:
    path = CATALOGUES / name
    if name.endswith(".json"):
        return path.read_bytes()
    return orjson.dumps(yaml.safe_load(path.read_text(encoding="utf-8")))
