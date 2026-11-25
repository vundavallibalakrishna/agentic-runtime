"""Example packs install, settings validate, and a script run is reproducible.

Label: unit
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import orjson
import pytest

from ar_common.errors import ValidationFailedError
from ar_contracts.definitions import ContentPack
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService
from ar_domain.config_docs.book import SettingsBook
from ar_domain.connectors.catalog import connector_by_slug
from ar_domain.connectors.token_exchange import headers_for_token, request_body
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.runs.logic import configured_run_budget
from ar_domain.tools.extensions import dispatch_extensions
from ar_domain.tools.registered import run_registered
from ar_testing.demo import demo_store

ROOT = Path(__file__).resolve().parents[4] / "packs" / "examples"


def _render(folder: Path) -> str:
    spec = importlib.util.spec_from_file_location("build_manifest", folder / "build_manifest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render()


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def test_pack_manifests_match_their_sources() -> None:
    for name in ("document-extraction", "horizon-scan", "scenario-runs"):
        folder = ROOT / name
        assert (folder / "manifest.json").read_text(encoding="utf-8") == _render(folder)
        ContentPack.model_validate(orjson.loads((folder / "manifest.json").read_bytes()))


def test_horizon_settings_are_versioned_and_rejected_when_invalid() -> None:
    store = demo_store()
    schema = orjson.loads((ROOT / "horizon-scan" / "settings.schema.json").read_bytes())
    document = orjson.loads((ROOT / "horizon-scan" / "settings.example.json").read_bytes())
    book = SettingsBook(store)
    saved = book.save(
        demo_id("tenant"), demo_id("admin"), "agent", "horizon-scan", schema, document
    )
    assert saved["version"] == 1
    again = book.save(
        demo_id("tenant"), demo_id("admin"), "agent", "horizon-scan", schema, document
    )
    assert again["version"] == 2
    with pytest.raises(ValidationFailedError):
        book.save(demo_id("tenant"), demo_id("admin"), "agent", "horizon-scan", schema, {})


def test_a_registered_script_rerun_has_the_same_hashes() -> None:
    script = (ROOT / "scenario-runs" / "examples" / "model.py").read_bytes()
    params = {"label": "synthetic"}
    first = run_registered(script, params, [])
    second = run_registered(script, params, [])
    assert first["ok"] is True
    assert first["script_sha256"] == second["script_sha256"]
    assert first["params_sha256"] == second["params_sha256"]
    assert first["output_hashes"] == second["output_hashes"]
    assert orjson.loads(first["stdout"])["units"] == 2


def test_compare_is_computed_in_code() -> None:
    result = dispatch_extensions(
        demo_store(),
        "compare",
        {"left": {"units": 2}, "right": {"units": 3}},
    )
    assert result["is_error"] is False
    assert result["structured"]["changes"] == [{"field": "units", "left": 2, "right": 3}]


def test_vendor_feed_row_is_not_live_and_posts_the_secret() -> None:
    row = connector_by_slug("lexisnexis-regulatory")
    assert row is not None
    assert row.verification == "not_live"
    assert "Not live-tested" in row.verification_note
    body = request_body(
        {"username": "ada@example.com", "authorize_url": "email:password:customerId"},
        "s3cret",
    )
    assert body == {"email": "ada@example.com", "password": "s3cret"}
    assert "s3cret" not in "https://example.test/token"
    headers = headers_for_token(
        {
            "header_name": "token",
            "authorize_url": "email:password:customerId",
            "client_id": "cust",
        },
        "minted",
    )
    assert headers["token"] == "minted"  # noqa: S105
    assert headers["customerId"] == "cust"
    assert "Bearer" not in headers["token"]


def test_the_routine_default_comes_from_settings() -> None:
    budget = configured_run_budget()
    assert budget["max_steps"] >= 16
    assert budget["max_tool_calls"] >= 16


def test_example_packs_install() -> None:
    actor = _actor()
    for name in ("document-extraction", "horizon-scan", "scenario-runs"):
        store = demo_store()
        manifest = orjson.loads((ROOT / name / "manifest.json").read_bytes())
        done = PackService(store).install(actor, manifest, signature=None, key_id=None)
        assert done["status"] == "installed"
