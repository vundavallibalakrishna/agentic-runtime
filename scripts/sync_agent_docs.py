"""Keep Claude's instructions identical to the Cursor agent instructions.

``AGENTS.md`` is the authored source (the spec). Claude Code reads ``CLAUDE.md``.
``make gen`` rewrites ``CLAUDE.md`` from ``AGENTS.md`` so the two cannot drift.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "AGENTS.md"
TARGET = ROOT / "CLAUDE.md"
BANNER = (
    "<!-- Generated from AGENTS.md by scripts/sync_agent_docs.py. "
    "Edit AGENTS.md, then run make gen. -->\n\n"
)


def render(agents: str) -> str:
    """Return the Claude file for an AGENTS.md body."""
    body = agents
    if body.startswith("<!-- Generated from AGENTS.md"):
        body = body.split("\n\n", 1)[1]
    if not body.endswith("\n"):
        body += "\n"
    return BANNER + body


def main() -> None:
    text = render(SOURCE.read_text(encoding="utf-8"))
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
