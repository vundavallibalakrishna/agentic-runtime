"""Domain modules do not import each other's repositories or models."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "libs" / "ar_domain" / "src" / "ar_domain"


def test_modules_do_not_import_foreign_repositories_or_adapters() -> None:
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        module = "ar_domain." + ".".join(path.relative_to(ROOT).with_suffix("").parts)
        owner = module.split(".")[1] if module.count(".") else ""
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            target = node.module
            if target.startswith("ar_domain.") and target.count(".") >= 2:
                other = target.split(".")[1]
                if other != owner and (
                    target.endswith(".repository") or target.endswith(".models")
                ):
                    violations.append(f"{module} -> {target}")
            if target in {"qdrant_client", "fastembed"} and "store_qdrant" not in module:
                violations.append(f"{module} -> {target}")
            adapters = {
                "ar_domain.knowledge.store_pgvector",
                "ar_domain.knowledge.store_qdrant",
                "ar_domain.knowledge.store_memory",
            }
            if target in adapters and not module.endswith("knowledge.store"):
                violations.append(f"{module} -> {target}")
    assert violations == []
