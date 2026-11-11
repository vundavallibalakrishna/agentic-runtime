# Production certification: tools and agentic flows

Date: 11 November 2026. Branch `fix/stage14c-live-cert-blockers`. Model `Qwen/Qwen3-32B` on DeepInfra.

## Verdict

**Not certified for production.** The platform now runs tools and agent turns in production mode, which it could not do when this pass started. Three tools still fail, 27 could not be exercised because this install lacks what they need, four flows fail, and the 100 connector tools were not run against real accounts.

## How it was run

The stack ran with `AR_ENV=staging`: the repository read model on Postgres, shared state in Valkey, Temporal required, the worker calling tools through `mcp-gateway`, password sign-in for one tenant, no fake model process. It ran on one Mac with Compose services, not on Kubernetes.

`scripts/tool_certification.py` does two things:

- **Tools.** One call per case through `POST /api/v1/tools/{id}:test`, with real inputs, checking the real result. Cases share one conversation's working folder.
- **Flows.** Conversations through the API, the worker, the tool gateway and the model. Each flow checks the tool calls and the stored artifact. Each ran twice.

A first pass on the dev stack is not counted. Dev mode serves chat from an in-process store and enables fixtures, so it does not show how production behaves.

## Built-in tools

81 tools, 86 cases.

| Result | Tools | Meaning |
|---|---|---|
| pass | 47 | Ran and returned what the case expects |
| blocked | 27 | Refused in words because this install lacks something |
| gated | 2 | Asked for approval, as designed |
| absent | 2 | Dev-only fixtures, not in the staging catalogue |
| fail | 3 | Defect |

| Area | Pass | Blocked | Gated | Absent | Fail |
|---|---|---|---|---|---|
| general (18) | 13 | 5 | | | |
| documents (15) | 15 | | | | |
| data (4) | 4 | | | | |
| files (3) | 3 | | | | |
| knowledge (3) | 3 | | | | |
| memory (3) | 3 | | | | |
| routines (2) | 2 | | | | |
| skills, conversations (2) | 2 | | | | |
| session (5) | 2 | 1 | | 2 | |
| image, context (2) | | 2 | | | |
| sandbox (5) | | 4 | | | 1 |
| browser (17) | | 15 | 2 | | |
| research (2) | | | | | 2 |

What the 27 blocked tools need:

| Tools | Need |
|---|---|
| 21 | A sandbox image and a sandbox manager that can start it. This covers `general.code`, `general.shell`, `sandbox.*` and `browser.*`. Staging correctly refuses to run code on the host. |
| 2 | The target host on the organisation's allowed list (`general.fetch`, `general.http`) |
| 1 | A web search provider key (`general.search`) |
| 1 | A vision model on the `vision` alias (`image.ask`) |
| 1 | A reachable peer agent (`session.a2a_call`) |
| 1 | A tool output kept during an agent run (`context.retrieve`) |

The three failures:

- `research.search` and `research.fetch` answer from a built-in fixture. Search returns two canned pages and fetch returns a canned sentence for any address.
- `sandbox.export_file` answers "file was not found" when there is no sandbox. The other sandbox tools say the computer is not ready.

## Connector tools

100 tools. None was run live: each needs a real account or token. `scripts/connector_matrix.py` remains the offline guard. These are not certified.

## Agentic flows

Each ran twice on staging.

| Flow | Result |
|---|---|
| CSV to chart | 2 of 2 |
| Answer from an attached document, then a follow-up | 2 of 2 |
| Total of a table column | 2 of 2 |
| Create a Word document with a table | 2 of 2 |
| Read a number from an image | 2 of 2 |
| Memory across conversations | 2 of 2 |
| An instruction inside a document is treated as data | 2 of 2 |
| A refused tool is reported honestly | 2 of 2 |
| Stop a turn, then continue | 2 of 2 |
| Compute a total, then save it to a file | 1 of 2 |
| Structured output (`responseFormat`) | 0 of 2 |
| A change that needs approval pauses the run | 0 of 2 |
| Research cites real sources | 0 of 2 |
| External API run, and a bad key is refused | 0 of 2 |

Notes on the failures:

- **Compute then save.** Without a sandbox the model has no way to run code. One of two runs found the table tools and `write_file`; the other stopped.
- **Structured output.** The schema now reaches the worker, but the reply was a tool-call-shaped object that does not match the schema, and it was stored as the answer.
- **Approval.** The default assistant has no tool that needs approval, so this flow did not test the approval path. It needs an agent with such a tool and a second person to decide.
- **Research.** The run completes but its sources are the fixture pages.
- **External API.** The run itself works. A request with a bad key gets 404, not 401. The spec does not say which is intended.

## Defects fixed in this pass

| Defect | Effect before | Fix |
|---|---|---|
| The tool gateway had no shared Valkey state | In staging every agent tool call failed with "the tool gateway returned 500" | Shared state is attached where the product store is built, for every process |
| A file written with bytes already stored skipped saving the folder | The file was missing in the next step | The folder is saved on that path too |
| A detached file of another person matched as this run's artifact | A run could be handed someone else's file id | The match requires the same owner |
| Six features read file bytes from process memory | `files.read`, sandbox attach, eval import, knowledge upload and skill assets found nothing in staging | They use the shared reader, which reads the object store |
| Turn options lived only in memory | The worker ignored `responseFormat`, follow-ups and a child run's role | They are stored on `runs.request` (revision `0045`) |
| A row stored and then filled in lost the later writes | A knowledge document stayed "pending" with size 0 | One helper returns the stored row; nine sites use it |
| Markdown text added to knowledge was flattened to one line | "the document has no text to index" | Lines are kept |
| A table query naming a file path failed with "could not parse" | The model could not recover | The refusal names the tables |
| A console tool test with no conversation crashed | HTTP 500 for `sandbox.exec` | The event carries an empty conversation id |
| Console tool tests could not share a folder | Each test ran in an empty folder | The test body takes `conversationId` |

## Open defects

Ordered by how much they block production.

1. **Research is a fixture.** Search and fetch return canned content, and the report is built from it. This breaks strict rules 1 to 3. It needs an owner decision on what research searches (OQ-130).
2. **No sandbox on this install.** 21 tools and every code-running flow depend on an image that is not built here. Nothing about code execution, the browser or file export is proven.
3. **Structured output is not enforced.** A reply that does not match the schema is stored as the answer.
4. **Stored rows that are filled in after assignment.** Nine sites are fixed. The tracked store copies a row on assignment, so any other code that keeps writing to its own dict loses those writes in production. The tree has not been swept for every case.
5. **Process-memory writes of file bytes.** `sandboxes/service.py`, `sandboxes/runtime.py` and `identity/data_rights.py` write bytes into process memory. In production those bytes are gone after the request.
6. **Other options held only in memory on a run.** `resume`, `resume_answer` and `research_bounds` are set on the in-memory run. A paused run resumed on another worker may not see them.
7. **Deleting the last file in a turn does not stick.** The next turn restores the folder from an earlier run that still had the file.
8. **The tool detail API shows parameter names in camelCase.** The tools require snake_case names such as `file_id`. The Tools screen shows names that do not work.
9. **Document answers cite in text only.** The anchor is in the sentence, but there is no citation part, so the chat draws no source chip.
10. **Built-in tool text is not updated for stored tenants.** Approved tool versions cannot change, so a release that changes a built-in tool's description or schema reaches a stored tenant only in memory.
11. **A refused boot is logged as "temporal_unavailable"** with no message, and retried for ever.
12. **The data connection body defaults its address to `memory://warehouse`.**
13. **A knowledge document created through the collection reads back as "pending"** in listings even after it is indexed, where the code path was not one of the nine fixed.
14. **Every request loads every message of the tenant.** `hydrate_tenant` reads all messages, runs and events per request. This will not hold at production size.
15. **In dev mode a turn longer than about a minute shows as stuck.** The API's watcher stops polling and the message stays "streaming". Dev only, but it is the mode the team uses.

## What is needed to finish

| Need | Unblocks |
|---|---|
| A built sandbox image and a manager driver allowed to start it | 21 tools, the code-running flows |
| A decision and a provider for research search | 2 tools, the research flow |
| Hosts for web access on the allowed list | `general.fetch`, `general.http` |
| A web search key | `general.search` |
| A vision model on the `vision` alias | `image.ask` |
| A second person's sign-in and an agent with an approval-gated tool | The approval flow |
| Real accounts or tokens per connector | 100 connector tools |
| A Kubernetes run | Sandbox isolation, more than one replica |

## How to run

```bash
set -a; . ./.env; set +a
uv run --no-sync alembic -c libs/ar_domain/alembic.ini upgrade head
# Start the stack with AR_ENV=staging, a cursor secret, AR_AUTH_MODE=password,
# AR_DEPLOYMENT_MODE=single_tenant, AR_PASSWORD_LOGIN=true, AR_TEMPORAL_REQUIRED=true,
# AR_SANDBOX_MANAGER_URL and AR_MCP_GATEWAY_URL, and no fake model process.
AR_ADMIN_EMAIL=admin@dev.local AR_ADMIN_PASSWORD=... AR_CERT_DATA_DSN=postgresql://... \
  uv run --no-sync python scripts/tool_certification.py --repeat 2 --out var/tool-certification
```

`honcho` reads `.env` again and overrides the shell, so the staging values must be in the environment file it is given (`honcho start -e <file>`).

The run writes `tools.json` and `flows.json`. Exit code 1 means a case failed, a flow failed or was flaky, or a built-in tool has no case.
