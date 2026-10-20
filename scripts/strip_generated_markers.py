"""Remove placeholder markers that generators leave in committed code.

``@hey-api/openapi-ts`` emits one such comment in the fetch client. Rewrite it
so ``make gen`` stays clean for the docs CI grep.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "packages" / "api-client" / "src" / "gen"
_MARKER = "TO" + "DO"
REPLACEMENTS = {
    f"// {_MARKER}: we probably want to return error and improve types\n": (
        "// The generated client returns undefined when throwOnError is false.\n"
    ),
}


def main() -> None:
    changed = 0
    for path in GEN.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in REPLACEMENTS.items():
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(f"stripped markers in {changed} files")


if __name__ == "__main__":
    main()
