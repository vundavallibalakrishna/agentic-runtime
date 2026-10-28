"""Locust entrypoint. Spec: docs/08-quality/performance-budgets.md."""

import importlib.util
from pathlib import Path
from typing import Any


def _load(name: str) -> Any:
    path = Path(__file__).resolve().parent / "scenarios" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"ar_load_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing scenario {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ChatUser = _load("chat").ChatUser
ToolUser = _load("tools").ToolUser
__all__ = ["ChatUser", "ToolUser"]
