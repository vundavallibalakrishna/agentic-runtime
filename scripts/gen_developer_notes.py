"""Copy the developer notes into the web app, so the product shows what the repository says.

The notes are the Markdown files in ``docs/agent-api``. The web app cannot read the
repository when it runs, so ``make gen`` writes them into one JSON file it imports. CI's
codegen-drift job fails when a note changed and this was not run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "agent-api"
TARGET = ROOT / "apps" / "web" / "src" / "generated" / "developer-notes.json"
# The order a person meets them in. A note that is not listed is added after these.
ORDER = (
    "connect-your-platform",
    "getting-started",
    "documents-and-knowledge",
    "chat",
    "README",
    "samples",
    "without-the-console",
    "webhooks",
    "embed",
    "a2a",
    "known-differences",
)
_LINK = re.compile(r"\]\((?!https?://|#|/)([^)#]+?)\.md(#[^)]*)?\)")
_OUTSIDE = re.compile(r"\[([^\]]+)\]\((?!https?://|#|/|\?)[^)]*\)")


def notes() -> list[dict[str, str]]:
    names = [path.stem for path in sorted(SOURCE.glob("*.md"))]
    ordered = [name for name in ORDER if name in names]
    ordered += [name for name in names if name not in ORDER]
    found = []
    for name in ordered:
        text = (SOURCE / f"{name}.md").read_text(encoding="utf-8")
        title = next(
            (line[2:].strip() for line in text.splitlines() if line.startswith("# ")), name
        )
        # A link to another note opens that note in the product. A link to anything else
        # in the repository has nowhere to go there, so its words are kept and the link is not.
        body = _LINK.sub(
            lambda found: (
                f"](?note={found.group(1).lower()}{found.group(2) or ''})"
                if (SOURCE / f"{found.group(1)}.md").exists()
                else found.group(0)
            ),
            text,
        )
        body = _OUTSIDE.sub(r"\1", body)
        found.append({"slug": name.lower(), "title": title, "body": body})
    return found


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(notes(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
