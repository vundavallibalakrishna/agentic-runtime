"""Fail when a built-in tool has no certification case.

``scripts/tool_certification.py`` fails a certification run when the install has a
built-in tool that no case calls. That run takes a real install and a real model, so
a tool added without a case was only found there (certification run 13). This is the
same rule in seconds: it walks the seeded catalogue and the script's cases, and names
each tool with no case so the case is added in the change that adds the tool.

Connector tools are certified by their own matrix and are not listed here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from ar_domain.chat.service import ChatService
from ar_domain.tools import seed_tools

SCRIPT = Path(__file__).with_name("tool_certification.py")


def built_in_tools() -> set[str]:
    store = ChatService()
    seed_tools.seed(store)  # the built-in catalogue
    names = {str(row.get("qualified_name") or "") for row in store.tool_versions.values()}
    return {name for name in names if name and not name.startswith("connectors.")}


def covered_tools() -> set[str]:
    spec = importlib.util.spec_from_file_location("tool_certification_cases", SCRIPT)
    if spec is None or spec.loader is None:
        raise SystemExit("scripts/tool_certification.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {case.tool for case in module.all_cases()}


def main() -> int:
    missing = sorted(built_in_tools() - covered_tools())
    for name in missing:
        print(f"{name}: no case in scripts/tool_certification.py")
    if missing:
        print("Add a case for each tool above in the change that adds the tool.")
        return 1
    print("every built-in tool has a certification case")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
