"""Generate ``libs/ar_client`` from ``openapi.json``.

The generator writes a package tree only (``--meta none``). The workspace
``pyproject.toml`` and tests stay in place.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "libs" / "ar_client" / "src" / "ar_client"


def main() -> None:
    tool = shutil.which("openapi-python-client")
    if tool is None:
        raise SystemExit("openapi-python-client is required")
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "pkg"
        subprocess.run(  # noqa: S603
            [
                tool,
                "generate",
                "--path",
                str(ROOT / "openapi.json"),
                "--config",
                str(ROOT / "scripts" / "openapi-python-client.yaml"),
                "--meta",
                "none",
                "--output-path",
                str(dest),
                "--overwrite",
            ],
            check=True,
            cwd=ROOT,
        )
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(dest, TARGET)
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
