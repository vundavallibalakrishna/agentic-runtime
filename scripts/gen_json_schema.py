"""Export JSON Schema, TypeScript types, and Zod schemas from Pydantic models.

``ar_contracts`` is the source of truth (ADR-0017). ``make gen`` writes:

- ``packages/api-client/src/schemas/*.json`` via ``TypeAdapter.json_schema``
- ``*.ts`` via ``json-schema-to-typescript``
- ``*.zod.ts`` via ``json-schema-to-zod`` (Zod 4), after local ``$ref`` inlining
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import orjson
from pydantic import TypeAdapter

from ar_contracts import SCHEMA_MODELS
from ar_contracts.stream import RunEvent

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "packages" / "api-client" / "src" / "schemas"
ZOD_DEPTH = 32
BANNER = (
    "/* Generated from ar_contracts Pydantic models by scripts/gen_json_schema.py. "
    "Do not edit. */\n"
)


def _write_schema(name: str, model: object) -> tuple[str, dict[str, object]]:
    schema = TypeAdapter(model).json_schema()
    path = SCHEMA_DIR / f"{name}.json"
    payload = orjson.dumps(schema, option=orjson.OPT_INDENT_2)
    path.write_bytes(payload + b"\n")
    return name, schema


def _deref(node: object, defs: dict[str, object], seen: tuple[str, ...]) -> object:
    """Inline local ``#/$defs`` refs, keeping sibling keywords such as ``default``."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            def_name = ref.removeprefix("#/$defs/")
            if def_name in seen:
                raise SystemExit(f"cyclic $ref {def_name}")
            target = defs[def_name]
            if not isinstance(target, dict):
                raise SystemExit(f"$ref {def_name} is not an object")
            siblings = {key: value for key, value in node.items() if key != "$ref"}
            merged = {**target, **siblings}
            merged.pop("$defs", None)
            return _deref(merged, defs, (*seen, def_name))
        return {key: _deref(value, defs, seen) for key, value in node.items() if key != "$defs"}
    if isinstance(node, list):
        return [_deref(item, defs, seen) for item in node]
    return node


def _schema_export(name: str) -> str:
    return f"{name[:1].lower()}{name[1:]}Schema"


def _type_name(name: str, schema: dict[str, object]) -> str:
    title = schema.get("title")
    if isinstance(title, str) and title:
        return title
    return name


def _pnpm() -> str:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm is required")
    return pnpm


def _emit_typescript(pnpm: str, name: str) -> None:
    schema = SCHEMA_DIR / f"{name}.json"
    out = SCHEMA_DIR / f"{name}.ts"
    subprocess.run(  # noqa: S603
        [
            pnpm,
            "--filter",
            "@ar/api-client",
            "exec",
            "json2ts",
            "--input",
            str(schema),
            "--output",
            str(out),
            "--unreachableDefinitions",
        ],
        check=True,
        cwd=ROOT,
    )


def _emit_zod(pnpm: str, name: str, schema: dict[str, object]) -> None:
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        raise SystemExit(f"{name} $defs is not an object")
    inlined = _deref(schema, defs, ())
    export = _schema_export(name)
    dest = SCHEMA_DIR / f"{name}.zod.ts"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"{name}.json"
        src.write_bytes(orjson.dumps(inlined))
        subprocess.run(  # noqa: S603
            [
                pnpm,
                "--filter",
                "@ar/api-client",
                "exec",
                "json-schema-to-zod",
                "--input",
                str(src),
                "--output",
                str(dest),
                "--name",
                export,
                "--depth",
                str(ZOD_DEPTH),
                "--module",
                "esm",
                "--zodVersion",
                "4",
            ],
            check=True,
            cwd=ROOT,
        )
    text = dest.read_text(encoding="utf-8")
    # `z.record(z.string(), z.any())` is a free-form JSON object (Pydantic `dict[str, Any]`).
    # Any other `z.any()` means the converter stopped early.
    if "z.any(" in text.replace("z.record(z.string(), z.any())", ""):
        raise SystemExit(f"{name} Zod schema fell back to z.any(); raise ZOD_DEPTH")
    if not text.endswith("\n"):
        text += "\n"
    dest.write_text(BANNER + text, encoding="utf-8")


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    models: list[tuple[str, object]] = [("RunEvent", RunEvent), *SCHEMA_MODELS.items()]
    written = [_write_schema(name, model) for name, model in models]
    pnpm = _pnpm()
    lines = ["/* Generated from ar_contracts Pydantic models. Do not edit. */"]
    for name, schema in written:
        _emit_typescript(pnpm, name)
        _emit_zod(pnpm, name, schema)
        # Root type only. `export type *` collides (`Name`, `Description`, …) across models.
        lines.append(f'export type {{ {_type_name(name, schema)} }} from "./{name}";')
        lines.append(f'export {{ {_schema_export(name)} }} from "./{name}.zod";')
    (SCHEMA_DIR / "index.ts").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(written)} schemas")


if __name__ == "__main__":
    main()
