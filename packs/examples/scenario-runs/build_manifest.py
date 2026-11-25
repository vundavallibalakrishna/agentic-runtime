"""Write manifest.json for the scenario runs example pack."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

INSTRUCTIONS = """You coordinate scenario records. You never state a number the registered script did not print.

1. Store a scenario with `extensions.put` (packId `scenario_runs`, bucket `scenarios`). A change
   is a new version and must include a reason.
2. Register a script by storing its file id and hash in bucket `models`.
3. Run it with `general.run_entry`. The entry point is the install setting. Do not invent a command.
4. Store the run, including the hashes the tool returned, in bucket `runs`.
5. Compare two runs with `extensions.compare`. Do not subtract figures yourself.
6. A scenario is agreed only after a multi-level review. Results are approved with four-eyes,
   and the preparer is not an approver. A report is issued only through `documents.create`
   after that approval.

`examples/model.py` in this pack is synthetic and is for tests only.
"""


def manifest() -> dict[str, object]:
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {
            "id": "scenario_runs",
            "version": "1.0.0",
            "name": "Scenario runs",
            "minPlatform": "1.0.0",
        },
        "spec": {
            "resources": [
                {
                    "kind": "Agent",
                    "metadata": {"slug": "scenario-runs", "name": "Scenario runs"},
                    "spec": {
                        "persona": {
                            "displayName": "Scenario runs",
                            "greeting": "I record scenarios, run a registered script, and keep the hashes.",
                        },
                        "instructions": INSTRUCTIONS,
                        "starterPrompts": ["Record a scenario version"],
                        "tools": [
                            {"server": "extensions", "include": ["put", "get", "list", "compare"]},
                            {"server": "general", "include": ["run_entry"]},
                            {"server": "documents", "include": ["read", "create"]},
                            {"server": "knowledge", "include": ["search"]},
                        ],
                        "skills": [],
                        "budget": {
                            "maxSteps": 24,
                            "maxTokens": 80000,
                            "maxCostMicros": 4000000,
                            "maxWallClockS": 900,
                            "maxToolCalls": 24,
                            "maxParallelToolCalls": 1,
                        },
                        "settingsSchema": {
                            "type": "object",
                            "required": ["approvalGroup"],
                            "additionalProperties": False,
                            "properties": {"approvalGroup": {"type": "string"}},
                        },
                        "settings": {"approvalGroup": "scenario-reviewers"},
                    },
                },
                {
                    "kind": "Policy",
                    "metadata": {"name": "Scenario approvals"},
                    "spec": {
                        "document": {
                            "rules": [
                                {
                                    "id": "scenario-agreed",
                                    "effect": "require_approval",
                                    "message": "Agreeing a scenario needs more than one approver.",
                                    "match": {"tools": ["extensions.put"]},
                                    "approval": {
                                        "approvers": {
                                            "mode": "group",
                                            "groups": ["{{approvalGroup}}"],
                                        },
                                        "required_approvals": 2,
                                        "four_eyes": False,
                                        "step_up": False,
                                        "ttl_s": 86400,
                                    },
                                },
                                {
                                    "id": "results-four-eyes",
                                    "effect": "require_approval",
                                    "message": "Results need a second person. The preparer cannot approve.",
                                    "match": {"tools": ["extensions.compare"]},
                                    "approval": {
                                        "approvers": {
                                            "mode": "group",
                                            "groups": ["{{approvalGroup}}"],
                                        },
                                        "required_approvals": 1,
                                        "four_eyes": True,
                                        "step_up": False,
                                        "ttl_s": 86400,
                                    },
                                },
                                {
                                    "id": "report-issued",
                                    "effect": "require_approval",
                                    "message": "A report is issued through document creation after approval.",
                                    "match": {"tools": ["documents.create"]},
                                    "approval": {
                                        "approvers": {
                                            "mode": "group",
                                            "groups": ["{{approvalGroup}}"],
                                        },
                                        "required_approvals": 1,
                                        "four_eyes": False,
                                        "step_up": False,
                                        "ttl_s": 86400,
                                    },
                                },
                            ]
                        }
                    },
                },
            ]
        },
    }


def render() -> str:
    return json.dumps(manifest(), indent=2) + "\n"


if __name__ == "__main__":
    (HERE / "manifest.json").write_text(render(), encoding="utf-8")
