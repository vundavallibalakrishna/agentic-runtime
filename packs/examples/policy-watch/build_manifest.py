"""Write manifest.json from the pack's source files.

Run from the repository root: ``uv run python packs/examples/policy-watch/build_manifest.py``.
The agent's instructions and the source list are kept as Markdown so they can be read and
reviewed; the manifest is what is installed.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

BUDGET = {
    "maxSteps": 40,
    "maxTokens": 400000,
    "maxCostMicros": 20000000,
    "maxWallClockS": 1200,
    "maxToolCalls": 60,
    "maxParallelToolCalls": 1,
}

DIGEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["changes", "newItems", "couldNotCheck"],
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "url", "before", "after", "nextStep"],
                "properties": {
                    "source": {"type": "string"},
                    "url": {"type": "string"},
                    "before": {"type": "string"},
                    "after": {"type": "string"},
                    "effectiveDate": {"type": "string"},
                    "affectedPolicies": {"type": "array", "items": {"type": "string"}},
                    "nextStep": {"type": "string"},
                },
            },
        },
        "newItems": {"type": "array", "items": {"type": "string"}},
        "couldNotCheck": {"type": "array", "items": {"type": "string"}},
    },
}


def manifest() -> dict[str, object]:
    """The content pack as it is installed."""
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {
            "id": "policy_watch",
            "version": "1.0.1",
            "name": "Policy watch",
            "minPlatform": "1.0.0",
        },
        "spec": {
            "resources": [
                {
                    "kind": "Skill",
                    "metadata": {"slug": "policy-watch-sources", "name": "Policy watch sources"},
                    "spec": {
                        "description": "The public sources the policy watch reads, and its "
                        "settings. Edit to change what is watched.",
                        "visibility": "tenant",
                        "requiredTools": [],
                        "instructionsMd": (HERE / "sources.md").read_text(encoding="utf-8"),
                    },
                },
                {
                    "kind": "Agent",
                    "metadata": {"slug": "policy-watch", "name": "Policy watch"},
                    "spec": {
                        "persona": {
                            "displayName": "Policy watch",
                            "greeting": "I check the watched sources and report what changed.",
                        },
                        "instructions": (HERE / "agent.md").read_text(encoding="utf-8"),
                        "starterPrompts": ["Run the policy watch now"],
                        "tools": [
                            {"server": "skills", "include": ["load"]},
                            {"server": "web", "include": ["discover"]},
                            {"server": "general", "include": ["fetch"]},
                            {
                                "server": "documents",
                                "include": [
                                    "list",
                                    "ingest",
                                    "diff",
                                    "read",
                                    "outline",
                                    "search",
                                    "create",
                                ],
                            },
                            {"server": "knowledge", "include": ["search", "list_collections"]},
                        ],
                        "skills": ["policy-watch-sources"],
                        "budget": BUDGET,
                        "taskTemplates": [
                            {
                                "id": "policy-watch-digest",
                                "prompt": "Write the policy watch digest: each change that "
                                "matters with the words before and after, the date it takes "
                                "effect, the policies it touches and one next step; then the "
                                "new items and the sources that could not be checked.",
                                "outputSchema": DIGEST_SCHEMA,
                            }
                        ],
                    },
                },
                {
                    "kind": "Routine",
                    "metadata": {"name": "Policy watch"},
                    "spec": {
                        "description": "Checks the watched sources twice a day and reports "
                        "what changed.",
                        "agent": "policy-watch",
                        "instructions": "Run the policy watch now. Follow your instructions "
                        "and the policy-watch-sources skill.",
                        "trigger": {
                            "type": "schedule",
                            "cron": "0 7,13 * * *",
                            "timezone": "Asia/Kolkata",
                        },
                        "delivery": [],
                        "budget": BUDGET,
                        "maxRunsPerDay": 4,
                        "concurrencyPolicy": "skip",
                    },
                },
            ]
        },
    }


def render() -> str:
    return json.dumps(manifest(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    (HERE / "manifest.json").write_text(render(), encoding="utf-8")
