"""The policy watch pack installs, and what it installs can be published and turned on."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from typing import Any

import orjson

from ar_contracts.definitions import ContentPack
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService
from ar_domain.agents.service import AgentLifecycle
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.routines.book import RoutineBook
from ar_domain.skills.book import SkillBook
from ar_domain.tools.seed_tools import shipped_tools
from ar_testing.demo import demo_store

PACK = Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, Any]:
    return orjson.loads((PACK / "manifest.json").read_bytes())  # type: ignore[no-any-return]


def _resource(kind: str) -> dict[str, Any]:
    return next(item for item in _manifest()["spec"]["resources"] if item["kind"] == kind)


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def _installed() -> tuple[Any, dict[str, dict[str, Any]]]:
    store = demo_store()
    done = PackService(store).install(_actor(), _manifest(), signature=None, key_id=None)
    assert done["status"] == "installed"
    return store, {row["kind"]: row for row in done["import_results"]}  # type: ignore[union-attr]


def test_the_manifest_is_what_the_source_files_build() -> None:
    spec = importlib.util.spec_from_file_location("build_manifest", PACK / "build_manifest.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (PACK / "manifest.json").read_text(encoding="utf-8") == module.render()


def test_the_manifest_is_a_content_pack_the_boot_loader_does_not_pick_up() -> None:
    parsed = ContentPack.model_validate(_manifest())
    assert parsed.metadata.id == "policy_watch"
    # The boot loader mounts packs/<name>/manifest.json. An example pack is installed by a
    # person through the product, so it must not sit where the loader looks.
    assert PACK not in {path.parent for path in PACK.parents[1].glob("*/manifest.json")}


def test_the_agent_is_granted_only_tools_this_release_ships() -> None:
    shipped = set(shipped_tools())
    granted = {
        f"{binding['server']}.{name}"
        for binding in _resource("Agent")["spec"]["tools"]
        for name in binding["include"]
    }
    assert granted <= shipped
    assert {"web.discover", "documents.ingest", "documents.diff", "skills.load"} <= granted
    # It reads and reports. It is given nothing that edits a policy or calls out freely.
    assert not granted & {"documents.edit", "general.http", "general.shell", "general.code"}


def test_installing_brings_the_skill_the_agent_and_a_paused_routine() -> None:
    store, results = _installed()
    assert {kind: row["action"] for kind, row in results.items()} == {
        "Skill": "create",
        "Agent": "create",
        "Routine": "create",
    }
    routine = store.routines[uuid.UUID(results["Routine"]["id"])]
    assert (routine["status"], routine["paused_reason"]) == ("paused", "imported")
    assert routine["trigger_config"]["cron"] == "0 7,13 * * *"
    assert routine["budget"]["max_tool_calls"] == 60
    assert str(routine["agent_id"]) == str(results["Agent"]["id"])
    skill = store.skills[uuid.UUID(str(results["Skill"]["id"]))]
    assert skill["slug"] == "policy-watch-sources"


def test_what_was_installed_can_be_published_and_turned_on() -> None:
    store, results = _installed()
    actor = _actor()
    skill_id = uuid.UUID(str(results["Skill"]["id"]))
    agent_id = uuid.UUID(str(results["Agent"]["id"]))
    SkillBook(store).publish(actor, skill_id)
    AgentLifecycle(store).publish(actor, agent_id)
    assert store.agents[agent_id].get("published_version_id") is not None
    resumed = RoutineBook(store).resume(actor, uuid.UUID(results["Routine"]["id"]))
    assert resumed["status"] == "active"
