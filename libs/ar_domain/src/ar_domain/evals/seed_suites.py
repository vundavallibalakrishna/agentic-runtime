"""Load repository suites into a tenant. Spec: docs/03-specs/18-observability-eval.md §4.5."""

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor


def suite_root() -> Path | None:
    """Repository ``evals/`` directory, when this checkout has one."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        root = parent / "evals"
        if (root / "redteam").is_dir() or (root / "golden").is_dir():
            return root
    return None


def suite_name(path: Path) -> str:
    """Name declared in one repository suite file."""
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return str(loaded.get("name") or "")
    return ""


def load_documents() -> list[dict[str, object]]:
    """YAML suites shipped with the product."""
    root = suite_root()
    if root is None:
        return []
    documents: list[dict[str, object]] = []
    for folder in ("redteam", "golden"):
        path = root / folder
        if not path.is_dir():
            continue
        for file in sorted(path.glob("*.yaml")):
            loaded = yaml.safe_load(file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                documents.append({str(key): value for key, value in loaded.items()})
    return documents


def install_platform(book: Any, actor: Actor) -> int:
    """Create missing platform suites. Existing names are left alone."""
    created = 0
    for document in load_documents():
        name = str(document.get("name") or "")
        if not name or _named(book, actor, name):
            continue
        suite = book.create_suite(
            actor,
            {
                "name": name,
                "description": str(document.get("description") or ""),
                "kind": str(document.get("kind") or "functional"),
                "agent_id": None,
                "gate": document.get("gate") or {"required": False},
            },
        )
        suite_id = suite["id"]
        cases = document.get("cases")
        if isinstance(cases, list):
            for case in cases:
                if isinstance(case, dict):
                    book.create_case(actor, suite_id, case)
        created += 1
    return created


def _named(book: Any, actor: Actor, name: str) -> bool:
    return any(str(row.get("name")) == name for row in book.list_suites(actor))
