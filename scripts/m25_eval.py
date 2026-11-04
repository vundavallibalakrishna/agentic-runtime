"""Retrieval eval for the indexed M25 proof library. Numbers come from this run."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import httpx
import orjson

BASE = os.environ.get("M25_API", "http://127.0.0.1:18125")
ROOT = Path(os.environ.get("M25_ROOT", str(Path(tempfile.gettempdir()) / "m25-proof")))

QUESTIONS = [
    {
        "id": "dock-code",
        "query": "What is the warehouse code for the north dock?",
        "expect": "ND-1844-QUILL",
    },
    {
        "id": "gpl-freedom",
        "query": "What does free software mean in the GNU GPL version 3?",
        "expect": "freedom, not price",
    },
    {
        "id": "rfc-protocol",
        "query": "What protocol does RFC 9110 specify?",
        "expect": "Hypertext Transfer Protocol",
    },
    {
        "id": "nist-ac2",
        "query": "What is control AC-2 about in NIST SP 800-53?",
        "expect": "AC-2",
    },
]


def main() -> None:
    state = orjson.loads((ROOT / "state.json").read_bytes())
    client = httpx.Client(base_url=BASE, timeout=120.0, follow_redirects=False)
    response = client.post("/api/v1/auth/dev-login", params={"email": "admin@dev.local"})
    if response.status_code not in {200, 302, 303}:
        raise SystemExit(f"dev login failed: {response.status_code}")
    token = client.cookies.get("ar_csrf")
    if not token:
        raise SystemExit("missing csrf")
    client.headers["x-csrf-token"] = token
    recalled = 0
    cited = 0
    rows = []
    for question in QUESTIONS:
        found = client.post(
            "/api/v1/knowledge/search",
            json={
                "query": question["query"],
                "collectionIds": [state["collectionId"]],
                "topK": 5,
            },
        )
        body = found.json()
        hits = body.get("hits") if isinstance(body, dict) else []
        if not isinstance(hits, list):
            hits = []
        top = hits[:5]
        match = None
        for hit in top:
            if isinstance(hit, dict) and question["expect"].lower() in json.dumps(hit).lower():
                match = hit
                break
        ok = match is not None
        has_anchor = False
        if isinstance(match, dict):
            has_anchor = bool(match.get("anchor") or match.get("page") is not None)
        has_citation = bool(ok and has_anchor)
        recalled += int(ok)
        cited += int(has_citation)
        rows.append(
            {
                "id": question["id"],
                "recalled": ok,
                "citation": has_citation,
                "page": None if not isinstance(match, dict) else match.get("page"),
                "anchor": None if not isinstance(match, dict) else match.get("anchor"),
            }
        )
    total = len(QUESTIONS)
    report = {
        "questions": total,
        "recalled": recalled,
        "recall": recalled / total,
        "cited": cited,
        "rows": rows,
    }
    path = ROOT / "eval.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
