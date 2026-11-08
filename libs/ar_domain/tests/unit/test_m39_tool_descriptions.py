"""Every built-in tool parameter is described, and the lint catches a gap. Task: M39-T01."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "check_tool_descriptions.py"


def _lint() -> Any:
    spec = importlib.util.spec_from_file_location("check_tool_descriptions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_builtin_parameter_is_described() -> None:
    lint = _lint()
    tools = lint._seed_catalogue()
    gaps: list[str] = []
    for tool in tools:
        qualified = str(tool.get("qualified_name") or tool.get("name"))
        if qualified.split(".", 1)[0] in lint.DEFERRED_SERVERS:
            continue
        schema = tool.get("input_schema")
        if isinstance(schema, dict):
            gaps.extend(lint._schema_gaps(qualified, schema))
    assert gaps == [], f"undescribed tool parameters: {gaps[:10]}"


def test_the_lint_finds_a_missing_description() -> None:
    lint = _lint()
    schema = {
        "type": "object",
        "properties": {
            "good": {"type": "string", "description": "has one"},
            "bad": {"type": "string"},
            "list": {"type": "array"},  # no item schema
        },
    }
    gaps = lint._schema_gaps("demo.tool", schema)
    assert "demo.tool.bad" in gaps
    assert any("demo.tool.list" in gap for gap in gaps)
    assert "demo.tool.good" not in gaps


def test_item_and_object_schemas_are_checked_deeply() -> None:
    lint = _lint()
    schema = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "description": "rows",
                "items": {
                    "type": "object",
                    "properties": {"cell": {"type": "string"}},  # cell has no description
                },
            }
        },
    }
    gaps = lint._schema_gaps("demo.tool", schema)
    assert "demo.tool.rows[].cell" in gaps


def test_no_server_is_deferred_from_description() -> None:
    lint = _lint()
    assert lint.DEFERRED_SERVERS == set()


def test_connector_parameters_are_described() -> None:
    from ar_domain.connectors.catalog import tool_records

    gaps: list[str] = []
    lint = _lint()
    for tool in tool_records():
        schema = tool.get("input_schema")
        if isinstance(schema, dict):
            gaps.extend(lint._schema_gaps(str(tool.get("name")), schema))
    assert gaps == [], f"undescribed connector parameters: {gaps[:10]}"


@pytest.mark.skipif(not SCRIPT.exists(), reason="lint script missing")
def test_the_lint_script_passes_on_the_real_catalogue() -> None:
    result = subprocess.run(  # noqa: S603 — the script path is from this repo, not user input
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    assert result.returncode == 0, result.stderr
