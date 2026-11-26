"""Fail when the developer notes and the API have drifted apart.

The notes under ``docs/agent-api`` are what an integrator follows, in the repository and
in the product. Two things keep them true:

1. Every API address a note names exists in the API (``openapi.json``). A call that was
   renamed or removed fails here until the note is corrected.
2. Every call an outside system is meant to use is named in some note: all of the agent
   API (``/v1``), and the families listed in ``MUST_COVER``. A new call in one of them
   fails here until a note says what it is for.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import orjson

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs" / "agent-api"
# Families of /api/v1 that integrators are sent to. A new call under one needs a note.
MUST_COVER = (
    "/api/v1/widget/",
    "/api/v1/files:upload",
    "/api/v1/files:limits",
    "/api/v1/library-documents",
    "/api/v1/knowledge/collections",
    "/api/v1/knowledge/search",
    "/api/v1/knowledge/sources/{source_id}:sync",
    "/api/v1/knowledge/jobs/{job_id}",
    "/api/v1/service-accounts",
    "/api/v1/api-keys",
    "/api/v1/openai/",
)
# Calls in those families that the product's own screens use and an integrator does not.
NOT_FOR_INTEGRATORS = (
    "/api/v1/widget/files",
    "/api/v1/widget/runs/{run_id}:cancel",
    "/api/v1/widget/conversations/{conversation_id}",
    "/api/v1/library-documents/{document_id}/outline",
    "/api/v1/library-documents/{document_id}/tables",
    "/api/v1/library-documents/{document_id}/extractions",
    "/api/v1/library-documents/{document_id}:reprocess",
    "/api/v1/library-documents/{document_id}/revisions",
    "/api/v1/knowledge/collections/{collection_id}:reindex",
    "/api/v1/knowledge/collections/{collection_id}/acl",
    "/api/v1/knowledge/collections/{collection_id}/stats",
    "/api/v1/knowledge/collections/{collection_id}/sources/{source_id}",
)
_ADDRESS = re.compile(r"(/(?:api/v1|v1)/[A-Za-z0-9_\-./:{}$<>]*[A-Za-z0-9_}>])")
_SLUG = re.compile(r"/v1/agents/[a-z0-9][a-z0-9-]*(/|:|$)")
_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}|\$\{?[A-Z_]+\}?|<[^>/]+>|\{[a-z_A-Z]+\}")


def shape(path: str) -> str:
    """A path with every variable part written the same way, so two spellings compare."""
    path = _PLACEHOLDER.sub("{}", path.split("?", maxsplit=1)[0]).rstrip("/.")
    # A sample may name a real agent where the contract has a slug.
    return _SLUG.sub(r"/v1/agents/{}\1", path)


def api_paths() -> set[str]:
    found: set[str] = set()
    for name in ("openapi.json", "docs/agent-api/openapi.json"):
        found.update(orjson.loads((ROOT / name).read_bytes())["paths"])
    return found


def named_in_notes() -> dict[str, str]:
    """Each address a note names, and the note that names it."""
    found: dict[str, str] = {}
    for note in sorted(NOTES.glob("*.md")):
        text = note.read_text(encoding="utf-8").replace("{{BASE_URL}}", "")
        for address in _ADDRESS.findall(text):
            found.setdefault(address, note.name)
    return found


def main() -> int:
    paths = api_paths()
    shapes = {shape(path): path for path in paths}
    named = named_in_notes()
    problems: list[str] = []
    for address, note in sorted(named.items()):
        wanted = shape(address)
        # A note may name a family ("/api/v1/widget") or a call under it.
        if wanted not in shapes and not any(known.startswith(wanted + "/") for known in shapes):
            problems.append(f"{note} names {address}, which the API does not have")
    covered = {shape(address) for address in named}
    for path in sorted(paths):
        public = path.startswith("/v1/") or any(path.startswith(item) for item in MUST_COVER)
        if not public or path in NOT_FOR_INTEGRATORS or shape(path) in covered:
            continue
        problems.append(f"no note says what {path} is for")
    for problem in problems:
        print(problem)
    if not problems:
        print(f"developer notes match the API ({len(named)} addresses checked)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
