"""Compare docs/stack.md pins to uv.lock, pnpm-lock.yaml and image references."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK = (ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
UV_LOCK = (ROOT / "uv.lock").read_text(encoding="utf-8")
PNPM_LOCK = (ROOT / "pnpm-lock.yaml").read_text(encoding="utf-8")
_INFRA_PATHS = [
    ROOT / "compose.yaml",
    *ROOT.glob("images/**/*"),
    *ROOT.glob(".github/workflows/*.yml"),
]
INFRA = "\n".join(path.read_text(encoding="utf-8") for path in _INFRA_PATHS if path.is_file())

VERSION = re.compile(r"\d+\.\d+(?:\.\d+)?(?:[a-zA-Z]\d+)?")
PACKAGE = re.compile(r"\[\[package\]\]\nname = \"([^\"]+)\"\nversion = \"([^\"]+)\"")
SKIP_NAMES = {
    "docker engine + compose v2",
    "kubernetes",
    "helm",
    "greenmail",
    "vllm",
    "hugging face tei",
    "cloudnativepg operator",
    "argo cd",
    "cert-manager",
    "keda",
    "envoy gateway",
    "gvisor",
    "kata containers",
    "falco",
    "sql",
}


def uv_versions() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for name, version in PACKAGE.findall(UV_LOCK):
        found.setdefault(name, set()).add(version)
    return found


def names_of(cell: str) -> list[str]:
    cell = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell)
    cell = cell.replace("`", "")
    cell = re.sub(r"\([^)]*\)", "", cell)
    parts = [re.sub(r"\[.*?\]", "", part).strip() for part in cell.split(" / ")]
    names: list[str] = []
    previous = ""
    for part in parts:
        if not part or part == "-":
            continue
        if part.startswith("-") and previous:
            head = previous.rsplit("-", 1)[0]
            names.append(f"{head}{part}")
        else:
            names.append(part)
            previous = part
    return names


def versions_of(cell: str) -> list[str]:
    return VERSION.findall(cell.split("(", maxsplit=1)[0])


def images_of(cell: str) -> list[str]:
    return re.findall(r"`([^`]+/[^`]+:[^`]+)`", cell)


def rows(section: str) -> list[tuple[str, str, str]]:
    parsed: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Component", "Library", "Tool", "Standard"}:
            continue
        if set(cells[0]) <= {"-", " "}:
            continue
        parsed.append((cells[0], cells[1], line))
    return parsed


def section(start: str, end: str | None) -> str:
    body = STACK.split(start, 1)[1]
    if end:
        body = body.split(end, 1)[0]
    return body


def main() -> None:  # noqa: PLR0912, PLR0915
    errors: list[str] = []
    locked = uv_versions()
    python_text = section("## 2. Python backend", "## 3. Web app")
    js_text = section("## 3. Web app", "## 4. Platform")
    infra_text = section("## 4. Platform", "## 5. Protocols")
    ci_text = section("### CI and supply-chain", "## 5. Protocols")

    for raw_name, raw_version, _line in rows(python_text):
        if raw_name.lower() == "uv":
            actual = subprocess.check_output(["uv", "--version"], text=True)  # noqa: S607
            if "0.13.3" not in actual:
                errors.append(f"uv tool is {actual.strip()}")
            continue
        package_names = [name.lower().replace(" ", "-") for name in names_of(raw_name)]
        versions = versions_of(raw_version)
        if not package_names or not versions:
            errors.append(f"unparsed python row: {raw_name}")
            continue
        if len(versions) == 1:
            versions = versions * len(package_names)
        if len(versions) != len(package_names):
            errors.append(f"version count mismatch: {raw_name}")
            continue
        for name, version in zip(package_names, versions, strict=True):
            if name == "lefthook" and version not in PNPM_LOCK:
                errors.append(f"lefthook {version} missing from pnpm-lock")
                continue
            if name == "lefthook":
                continue
            have = locked.get(name, set())
            if version not in have:
                errors.append(f"{name} {version} not in uv.lock (have {sorted(have)})")

    for raw_name, raw_version, _line in rows(js_text):
        package_names = names_of(raw_name)
        versions = versions_of(raw_version)
        if raw_name.startswith("@radix-ui"):
            continue
        if not versions:
            errors.append(f"unparsed js row: {raw_name}")
            continue
        if len(versions) == 1:
            versions = versions * len(package_names)
        for name, version in zip(package_names, versions, strict=True):
            needle = f"{name}@{version}"
            if needle not in PNPM_LOCK:
                errors.append(f"{needle} missing from pnpm-lock.yaml")

    for raw_name, raw_version, _line in rows(infra_text):
        if raw_name.lower() in SKIP_NAMES:
            continue
        errors.extend(
            f"image {image} missing from compose or Dockerfiles"
            for image in images_of(raw_version) + images_of(raw_name)
            if image not in INFRA
        )

    for raw_name, raw_version, _line in rows(ci_text):
        versions = versions_of(raw_version)
        if not versions:
            continue
        if versions[0] not in INFRA and raw_name != "@mermaid-js/mermaid-cli (`mmdc`)":
            errors.append(f"CI pin {raw_name} {versions[0]} missing from workflows")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("stack pins match the lockfiles")


if __name__ == "__main__":
    main()
