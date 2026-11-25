"""Write manifest.json for the horizon scan example pack."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

INSTRUCTIONS = """You scan configured sources and propose candidate items. Load nothing from memory about
which sources matter: read the settings document for this agent first.

Settings hold sources (feeds, pages and search topics), categories, relevance criteria
as prose, and a review frequency. Apply the criteria as written. Do not invent a keyword list.

1. For each feed, call `web.discover`. For each page, ingest when the content changed and
   call `documents.diff` against the previous copy.
2. Score relevance against the criteria. Keep a reason and a link to the evidence.
3. Dedupe against earlier rows from `extensions.list` (packId `horizon_scan`, bucket `candidates`)
   by URL and content hash.
4. Store each new candidate with `extensions.put`.
5. If settings name a read tool for an external register, call it and suggest links by id.
   Do not create platform tables for that register.
6. Do not call the write tool named in `registerWriteTool` unless a person will approve it.
   That tool is gated. The approval group is `approvalGroup` in settings.
7. If nothing is new, call `routines.nothing_to_report`.

Never state a fact you cannot point at in a stored copy or a tool result.
"""


def manifest() -> dict[str, object]:
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {
            "id": "horizon_scan",
            "version": "1.0.0",
            "name": "Horizon scan",
            "minPlatform": "1.0.0",
        },
        "spec": {
            "resources": [
                {
                    "kind": "Agent",
                    "metadata": {"slug": "horizon-scan", "name": "Horizon scan"},
                    "spec": {
                        "persona": {
                            "displayName": "Horizon scan",
                            "greeting": "I scan the configured sources and propose items for review.",
                        },
                        "instructions": INSTRUCTIONS,
                        "starterPrompts": ["Scan the configured sources"],
                        "tools": [
                            {"server": "web", "include": ["discover"]},
                            {"server": "general", "include": ["search", "fetch"]},
                            {
                                "server": "documents",
                                "include": ["ingest", "diff", "read", "list", "create"],
                            },
                            {"server": "knowledge", "include": ["search"]},
                            {"server": "extensions", "include": ["put", "list"]},
                            {"server": "routines", "include": ["nothing_to_report"]},
                        ],
                        "skills": [],
                        "budget": {
                            "maxSteps": 40,
                            "maxTokens": 400000,
                            "maxCostMicros": 20000000,
                            "maxWallClockS": 1200,
                            "maxToolCalls": 60,
                            "maxParallelToolCalls": 1,
                        },
                    },
                },
                {
                    "kind": "Routine",
                    "metadata": {"name": "Horizon scan"},
                    "spec": {
                        "description": "Weekly scan. Sends only when there is something to report.",
                        "agent": "horizon-scan",
                        "instructions": "Scan the configured sources and follow your instructions.",
                        "trigger": {
                            "type": "schedule",
                            "cron": "0 7 * * 1",
                            "timezone": "UTC",
                        },
                        "delivery": [
                            {
                                "type": "webhook",
                                "when": "something_to_report",
                                "config": {"url": "https://example.com/horizon"},
                            }
                        ],
                        "budget": {
                            "maxSteps": 40,
                            "maxTokens": 400000,
                            "maxCostMicros": 20000000,
                            "maxWallClockS": 1200,
                            "maxToolCalls": 60,
                            "maxParallelToolCalls": 1,
                        },
                    },
                },
            ]
        },
    }


def render() -> str:
    return json.dumps(manifest(), indent=2) + "\n"


if __name__ == "__main__":
    (HERE / "manifest.json").write_text(render(), encoding="utf-8")
