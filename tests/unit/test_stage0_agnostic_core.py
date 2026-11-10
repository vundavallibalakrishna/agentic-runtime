"""Stage 0: the agent instructions do not keep the records product in core."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

ADRS = (
    "ADR-0028-agnostic-core.md",
    "ADR-0029-generic-judgements.md",
    "ADR-0030-production-topology.md",
    "ADR-0031-oidc-production-identity.md",
    "ADR-0032-proof-labels.md",
    "ADR-0033-postgres-read-model.md",
    "ADR-0034-signed-pack-model.md",
)

# A sentence that names the records product and then calls it generic core.
_CORE_GENERIC = re.compile(
    r"\b(binders|ai register|legal holds?)\b[^.]*\bare generic\b"
    r"|\bare generic\b[^.]*\b(binders|ai register|legal holds?)\b",
    re.IGNORECASE,
)


@pytest.mark.unit
def test_stage0_agnostic_core_docs() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert _CORE_GENERIC.search(agents) is None
    principle = _principle_three(agents)
    for name in ("binders", "ai register", "legal hold"):
        assert name in principle
        assert "pack" in principle
        assert "are generic" not in principle
    adr_dir = ROOT / "docs" / "02-architecture" / "adr"
    for name in ADRS:
        path = adr_dir / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "Status:" in text
        assert "Decision" in text


def _principle_three(agents: str) -> str:
    match = re.search(r"\n3\. \*\*.*?(?=\n4\. )", agents, flags=re.DOTALL)
    assert match is not None
    return match.group(0).lower()
