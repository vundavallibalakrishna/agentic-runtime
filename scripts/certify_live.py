#!/usr/bin/env python
"""Live certification against a real OpenAI-compatible model.

Proof label is ``live`` only when ``AR_LLM_API_KEY`` is set and the run finishes.
Without a key this writes a ``contract`` scorecard and exits 0. It does not
invent a model id or a screenshot.

Compose publishes the API on ``AR_PORT`` (default 8000) and the web app on
``AR_WEB_HOST_PORT`` (default 3000). Point ``AR_API_URL`` and ``AR_PUBLIC_URL``
at those origins.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_BASE = "https://api.deepinfra.com/v1/openai"
DEFAULT_MODEL = "Qwen/Qwen3.8-27B"
DEFAULT_EMBED = "Qwen/Qwen3-Embedding-8B"


def _api_url() -> str:
    """``AR_API_URL`` when set, otherwise ``http://127.0.0.1:$AR_API_PORT`` or ``AR_PORT``."""
    explicit = os.environ.get("AR_API_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    port = (
        os.environ.get("AR_API_PORT", "").strip() or os.environ.get("AR_PORT", "").strip() or "8000"
    )
    return f"http://127.0.0.1:{port}"


def guard_ports() -> list[str]:
    """A URL with no host is not an origin the certification can call."""
    problems: list[str] = []
    for name in ("AR_API_URL", "AR_PUBLIC_URL", "AR_WEB_URL"):
        raw = os.environ.get(name, "").strip()
        if raw and urllib.parse.urlparse(raw).hostname is None:
            problems.append(f"{name} is not an absolute URL")
    return problems


def scorecard(label: str, **extra: object) -> dict[str, object]:
    return {
        "label": label,
        "modelId": os.environ.get("AR_LLM_MODEL", DEFAULT_MODEL) if label == "live" else "",
        "date": datetime.now(UTC).date().isoformat(),
        "llmBaseUrl": os.environ.get("AR_LLM_BASE_URL", DEFAULT_BASE) if label == "live" else "",
        **extra,
    }


def write(path: Path, body: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(path)


def main() -> int:
    out = Path(os.environ.get("AR_CERT_OUT", "var/live-certification"))
    problems = guard_ports()
    if problems:
        write(
            out / "scorecard.json",
            scorecard("contract", live="pending", blocked=problems),
        )
        for item in problems:
            print(item, file=sys.stderr)
        return 2
    key = os.environ.get("AR_LLM_API_KEY", "").strip()
    if not key:
        write(
            out / "scorecard.json",
            scorecard(
                "contract",
                live="pending",
                reason="AR_LLM_API_KEY is not set. The live run is pending on the owner's machine.",
            ),
        )
        print("live certification pending: no AR_LLM_API_KEY")
        return 0
    missing = [
        name
        for name in (
            "AR_ADMIN_PASSWORD",
            "AR_SECOND_EMAIL",
            "AR_SECOND_PASSWORD",
            "AR_CERT_DOCUMENT",
            "AR_ADMIN_EMAIL",
        )
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        write(
            out / "scorecard.json",
            scorecard("contract", live="pending", reason="missing " + ", ".join(missing)),
        )
        print("live certification pending: " + ", ".join(missing))
        return 2
    api = _api_url()
    web = os.environ.get("AR_PUBLIC_URL", "").rstrip("/") or os.environ.get(
        "AR_WEB_URL", ""
    ).rstrip("/")
    if not api or not web:
        write(
            out / "scorecard.json",
            scorecard("contract", live="pending", reason="AR_API_URL and AR_WEB_URL are required"),
        )
        print("set AR_API_URL and AR_WEB_URL", file=sys.stderr)
        return 2
    import importlib.util  # noqa: PLC0415

    module_path = Path(__file__).with_name("live_certification_run.py")
    spec = importlib.util.spec_from_file_location("live_certification_run", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("live certification runner is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.run_live(api=api, web=web, out=out)
    write(out / "scorecard.json", report)
    return 0 if report.get("label") == "live" and report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
