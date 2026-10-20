"""AGENTS.md and CLAUDE.md stay the same instructions."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "sync_agent_docs",
    ROOT / "scripts" / "sync_agent_docs.py",
)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
render = _MODULE.render


def test_claude_file_matches_agents() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude == render(agents)
    assert agents in claude
    assert "Agentic Runtime" in claude
