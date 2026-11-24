#!/usr/bin/env python
"""Install the policy watch pack in the demo tenant and point it at the policy library.

The pack is ``packs/examples/policy-watch``. An install that requires signed packs needs
the signature and the key id: pass them as ``DEMO_PACK_SIGNATURE`` and ``DEMO_PACK_KEY_ID``.

    AR_API_URL=... AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \\
        uv run --no-sync python packs/examples/grc-flows/demo/scripts/setup_watch.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import orjson

HERE = Path(__file__).parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "scripts"))

import tool_certification as tc  # noqa: E402 - the signed-in client lives there

HOSTS = ["www.rbi.org.in", "rbi.org.in"]


def rows(found: object) -> list[dict[str, object]]:
    if isinstance(found, dict):
        found = found.get("items") or found.get("data") or []
    return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []


def main() -> int:
    stack = tc.Stack(
        os.environ["AR_API_URL"].rstrip("/"),
        os.environ["AR_ADMIN_EMAIL"],
        os.environ["AR_ADMIN_PASSWORD"],
    )
    current = stack.client.get("/api/v1/tenant")
    settings = current.json().get("settings") or {}
    hosts = sorted({*map(str, settings.get("egressAllowlist") or []), *HOSTS})
    done = stack.client.patch(
        "/api/v1/tenant",
        json={"settings": {"egressAllowlist": hosts}},
        headers={"If-Match": current.headers.get("etag", "")},
    )
    print("allowed hosts", done.status_code)

    if not any(
        row.get("slug") == "policy-watch" for row in rows(stack.get("/api/v1/agents", limit=200))
    ):
        body: dict[str, object] = {
            "manifest": orjson.loads(
                (REPO / "packs/examples/policy-watch/manifest.json").read_bytes()
            )
        }
        if os.environ.get("DEMO_PACK_SIGNATURE"):
            body["signature"] = os.environ["DEMO_PACK_SIGNATURE"]
            body["keyId"] = os.environ.get("DEMO_PACK_KEY_ID", "")
        status, installed = stack.post("/api/v1/content-packs:install", **body)
        print(
            "pack install", status, "" if status < 300 else orjson.dumps(installed).decode()[:300]
        )

    skill = next(
        row
        for row in rows(stack.get("/api/v1/skills"))
        if row.get("slug") == "policy-watch-sources"
    )
    detail = stack.get(f"/api/v1/skills/{skill['id']}")
    text = str(
        detail.get("instructionsMd") or (detail.get("draft") or {}).get("instructionsMd") or ""
    )
    if "internal_collections: []" in text:
        text = text.replace(
            "internal_collections: []", "internal_collections: [meridian-policy-library]"
        )
        saved = stack.client.patch(f"/api/v1/skills/{skill['id']}", json={"instructionsMd": text})
        print("sources point at the policy library", saved.status_code)
    print(
        "skill published",
        stack.post(f"/api/v1/skills/{skill['id']}:publish", changeNote="demo setup")[0],
    )

    agent = next(
        row
        for row in rows(stack.get("/api/v1/agents", limit=200))
        if row.get("slug") == "policy-watch"
    )
    print(
        "agent published",
        stack.post(f"/api/v1/agents/{agent['id']}:publish", changeNote="demo setup")[0],
    )
    routine = next(
        row for row in rows(stack.get("/api/v1/routines")) if row.get("name") == "Policy watch"
    )
    print("routine", routine.get("status"), routine.get("pausedReason") or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
