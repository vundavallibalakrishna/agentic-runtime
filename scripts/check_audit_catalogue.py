"""Parse the audit action catalogue and reject duplicates.

`ar_domain.audit.actions.AuditAction` is compared once that module exists (M1).
"""

import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "06-security" / "audit.md"
ACTION = re.compile(r"`([a-z][a-z0-9_.]*)`")


def catalogue() -> list[str]:
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## 3. Catalogue", 1)[1].split("## 4.", 1)[0]
    actions: list[str] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        for match in ACTION.findall(line):
            if match == "audit.event":
                continue
            actions.append(match)
    return actions


def main() -> None:
    actions = catalogue()
    duplicates = sorted({item for item in actions if actions.count(item) > 1})
    if not actions or duplicates:
        print(f"catalogue parse failed ({len(actions)} actions)", file=sys.stderr)
        if duplicates:
            print("duplicates:", ", ".join(duplicates), file=sys.stderr)
        raise SystemExit(1)
    try:
        module = importlib.import_module("ar_domain.audit.actions")
    except ModuleNotFoundError:
        print(f"{len(actions)} audit actions; enum arrives with M1")
        return
    documented = set(actions)
    declared = {item.value for item in module.AuditAction}
    if documented != declared:
        print("audit enum drifted from docs/06-security/audit.md", file=sys.stderr)
        raise SystemExit(1)
    print(f"{len(actions)} audit actions match the enum")


if __name__ == "__main__":
    main()
