# Production certification: tools and agentic flows

Date: 11 November 2026. Branch `fix/stage14c-live-cert-blockers`. Model `Qwen/Qwen3-32B` on DeepInfra.

## Verdict

**Not certified for production.** The platform now runs tools and agent turns in production mode, which it could not do when this pass started. One tool still fails, 27 could not be exercised because this install lacks what they need, three flows fail, and the 100 connector tools were not run against real accounts.

## How it was run

The stack ran with `AR_ENV=staging`: the repository read model on Postgres, shared state in Valkey, Temporal required, the worker calling tools through `mcp-gateway`, password sign-in for one tenant, no fake model process. It ran on one Mac with Compose services, not on Kubernetes.

`scripts/tool_certification.py` does two things:

- **Tools.** One call per case through `POST /api/v1/tools/{id}:test`, with real inputs, checking the real result. Cases share one conversation's working folder.
- **Flows.** Conversations through the API, the worker, the tool gateway and the model. Each flow checks the tool calls and the stored artifact. Each ran twice.

A first pass on the dev stack is not counted. Dev mode serves chat from an in-process store and enables fixtures, so it does not show how production behaves.

## Built-in tools

81 tools, 87 cases. The last run was after the sandbox image was built.

| Result | Tools | Meaning |
|---|---|---|
| pass | 67 | Ran and returned what the case expects |
| blocked | 11 | Refused in words because this install lacks something |
| gated | 1 | Asked for approval, as designed |
| absent | 2 | Dev-only fixtures, not in the staging catalogue |
| fail | 0 | |

| Area | Pass | Blocked | Gated | Absent | Fail |
|---|---|---|---|---|---|
| general (18) | 15 | 3 | | | |
| documents (15) | 15 | | | | |
| data (4) | 4 | | | | |
| files (3) | 3 | | | | |
| knowledge (3) | 3 | | | | |
| memory (3) | 3 | | | | |
| routines (2) | 2 | | | | |
| skills, conversations (2) | 2 | | | | |
| session (5) | 2 | 1 | | 2 | |
| image, context (2) | | 2 | | | |
| sandbox (5) | 5 | | | | |
| browser (17) | 11 | 5 | 1 | | |
| research (2) | 2 | | | | |

What the 11 blocked tools need:

| Tools | Need |
|---|---|
| 3 | A page with a field, a file input and a download link on a host the browser may open (`browser.type`, `browser.upload`, `browser.download`). Set `AR_CERT_FORM_URL` and the element references. |
| 2 | A stored browser sign-in (`browser.save_session`, `browser.use_connection`) |
| 2 | The target host on the organisation's allowed list (`general.fetch`, `general.http`) |
| 1 | A web search provider key (`general.search`) |
| 1 | A vision model on the `vision` alias (`image.ask`) |
| 1 | A reachable peer agent (`session.a2a_call`) |
| 1 | A tool output kept during an agent run (`context.retrieve`) |

### The sandbox

The image `ar-sandbox:dev` was built from `images/sandbox/Dockerfile` (4.5 GB, with Chromium, LibreOffice and the data libraries). The sandbox manager ran with the docker driver and started one container per conversation. Inside real containers:

- `general.code` and `general.shell` ran, and the files they wrote came back as artifacts.
- `sandbox.exec`, `write_file`, `read_file`, `list_files` and `export_file` ran, and a file attached with `files.attach_to_sandbox` was readable.
- The browser opened `https://example.com` in Chromium and read it, took a screenshot, saved a PDF, scrolled, pressed a key, opened, switched and closed tabs, and followed a link. A click that names no element is refused at once in words.

The browser cases run as an agent whose computer uses the browser template, because the default template has no browser. A console test in a conversation now runs as that conversation's agent.

Building the image was not enough. Six defects kept a computer from working in production mode, and all are fixed (see the table below). What is still open for a computer is in [OQ-132](../../open-questions.md): the Kubernetes driver's image, suspend, and network confinement of the docker driver.

Research was a fixture when this pass began: search returned two canned pages and fetch a canned sentence. It now searches the tenant's document library and, when a provider is configured, the web. Both research tools pass on library passages. Web results were not exercised, because no provider is configured here.

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
| Research cites real sources | 3 of 3 |
| External API run, and a bad key is refused | 0 of 2 |

Notes on the failures:

- **Compute then save.** Without a sandbox the model has no way to run code. One of two runs found the table tools and `write_file`; the other stopped.
- **Structured output.** The schema now reaches the worker, but the reply was a tool-call-shaped object that does not match the schema, and it was stored as the answer.
- **Approval.** The default assistant has no tool that needs approval, so this flow did not test the approval path. It needs an agent with such a tool and a second person to decide.
- **Research.** Fixed after the first run: three of three runs cite passages of the tenant's library, and a question nothing matches gets a report that says where research looked.
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
| Research answered from a built-in fixture | Canned sources and a report built from them | Research searches the document library and the web provider `general.search` uses; the fixture is gone |
| The sandbox manager registered no docker driver | With the image built, no container was ever started | The manager starts containers from `AR_SANDBOX_IMAGE`; with no image a start fails and names the setting |
| The sandbox manager's routes used the read model without loading a tenant | Every `ensure` in production mode failed with HTTP 500 | Each route loads one tenant and saves what it changed |
| Only the worker was told to ask the manager for a computer | The tool gateway, which runs the tools, started nothing and said "the computer is not ready" | Every process but the manager is told where computers come from when its store is built |
| A computer's address and token were not saved | A second call could not reach the container | The address and token hash are saved; the token is sealed as a named secret and returned on each `ensure` |
| `general.code` and `general.shell` had no path into a computer | They were refused everywhere outside dev | They run in the conversation's computer; the run's folder is copied in and new files are copied back |
| `sandbox.export_file` read a host folder | "file was not found" when the computer is a container | It reads the file through the computer's agent, whole, window by window |
| A browser click with no element waited 30 seconds | The model got a timeout it could not act on | It is refused at once: "ref is required: take it from the last browser.snapshot" |
| A console tool test with no conversation crashed | HTTP 500 for `sandbox.exec` | The event carries an empty conversation id |
| Console tool tests could not share a folder | Each test ran in an empty folder | The test body takes `conversationId` |

## Open defects

Ordered by how much they block production.

1. **Research matches by words, not meaning.** A passage counts when it shares a distinctive word with the question. The report quotes the first sentence of each source and is not written by the model. A question phrased differently from the document can miss it.
2. **A computer is proven on one machine only.** The docker driver works in production mode. The Kubernetes driver starts pods from an image digest written in code, suspend does not stop a container, and the docker driver does not confine the network ([OQ-132](../../open-questions.md)).
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
| A page with a form on an allowed host, and a stored browser sign-in | 5 browser tools |
| An owner decision on where the Kubernetes sandbox image comes from | Computers on a cluster |
| A web search provider and key | Web results in research, `general.search` |
| Hosts for web access on the allowed list | `general.fetch`, `general.http` |
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
# AR_SANDBOX_MANAGER_URL and AR_MCP_GATEWAY_URL, and no fake model process. For computers on
# one machine also set AR_SANDBOX_DRIVER=docker, AR_SANDBOX_IMAGE=ar-sandbox:dev and
# AR_SANDBOX_ALLOW_UNISOLATED=true, after docker build -f images/sandbox/Dockerfile -t ar-sandbox:dev .
AR_ADMIN_EMAIL=admin@dev.local AR_ADMIN_PASSWORD=... AR_CERT_DATA_DSN=postgresql://... \
  uv run --no-sync python scripts/tool_certification.py --repeat 2 --out var/tool-certification
```

`honcho` reads `.env` again and overrides the shell, so the staging values must be in the environment file it is given (`honcho start -e <file>`).

The run writes `tools.json` and `flows.json`. Exit code 1 means a case failed, a flow failed or was flaky, or a built-in tool has no case.
