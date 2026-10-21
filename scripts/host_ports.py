"""Fail when a local host port is busy, or move it when AUTO_PORTS=1."""

import os
from pathlib import Path

from ar_common.host_ports import PortCheck, prepare_env_file

ROOT = Path(__file__).resolve().parents[1]


def _flag(name: str) -> bool:
    return os.environ.get(name, "0") == "1"


def main() -> None:
    """Sync ``.env`` URLs, then check or move host ports."""
    env_file = Path(os.environ.get("AR_ENV_FILE", str(ROOT / ".env")))
    code, report = prepare_env_file(
        env_file,
        PortCheck(
            auto=_flag("AUTO_PORTS"),
            dev_min=_flag("DEV_MIN"),
            obs=_flag("OBS"),
            scan=_flag("SCAN"),
            qdrant=_flag("QDRANT"),
        ),
        ROOT / ".env.example",
    )
    print(report)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
