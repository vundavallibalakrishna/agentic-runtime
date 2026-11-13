# Production certification: tools and agentic flows

Date: 11 and 12 November 2026. Branch `fix/stage14c-live-cert-blockers`. Model `Qwen/Qwen3-32B` on DeepInfra.

## Verdict

**Not certified for production.** On the last run no built-in tool fails and all 14 agent flows pass, which was true of neither when this pass started. What keeps it uncertified: 11 tools could not be exercised because this install lacks what they need, the sandbox is proven on one machine and not on Kubernetes, the 100 connector tools were not run against real accounts, the open defects below remain, and the Helm, kind, compose and security jobs have not been run on this branch.

## How it was run

The stack ran with `AR_ENV=staging`: the repository read model on Postgres, shared state in Valkey, Temporal required, the worker calling tools through `mcp-gateway`, password sign-in for one tenant, no fake model process. It ran on one Mac with Compose services, not on Kubernetes.

`scripts/tool_certification.py` does two things:

- **Tools.** One call per case through `POST /api/v1/tools/{id}:test`, with real inputs, checking the real result. Cases share one conversation's working folder.
- **Flows.** Conversations through the API, the worker, the tool gateway and the model. Each flow checks the tool calls and the stored artifact. Each ran twice.

A first pass on the dev stack is not counted. Dev mode serves chat from an in-process store and enables fixtures, so it does not show how production behaves.

## Built-in tools

81 tools, 89 cases. The last run was after the sandbox image was built. A case that names a stored file also downloads it, so a file whose bytes were lost fails.

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

Building the image was not enough. Six defects kept a computer from working in production mode, and all are fixed (see the table below). What is still open for a computer is in [OQ-132](../../open-questions.md): a run on a cluster, suspend, and network confinement of the docker driver.

Research was a fixture when this pass began: search returned two canned pages and fetch a canned sentence. It now searches the tenant's document library and, when a provider is configured, the web. Both research tools pass on library passages. Web results were not exercised, because no provider is configured here.

## Connector tools

100 tools. None was run live: each needs a real account or token. `scripts/connector_matrix.py` remains the offline guard. These are not certified.

## Agentic flows

Each ran twice on staging in one run of the whole script, on the final build with the sandbox.

| Flow | Result |
|---|---|
| CSV to chart | 2 of 2 |
| Answer from an attached document, then a follow-up | 2 of 2 |
| Total of a table column | 2 of 2 |
| Compute a total, then save it to a file | 2 of 2 |
| Create a Word document with a table | 2 of 2 |
| Read a number from an image | 0 of 2, then 4 of 4 after a fix |
| Memory across conversations | 2 of 2 |
| An instruction inside a document is treated as data | 2 of 2 |
| A refused tool is reported honestly | 2 of 2 |
| Structured output (`responseFormat`) | 2 of 2 |
| A change that needs approval pauses the run | 2 of 2 |
| Research cites real sources | 2 of 2 |
| External API run, and a bad key is refused | 2 of 2 |
| Stop a turn, then continue | 2 of 2 |

13 passed in that run. The image flow failed both times and was fixed afterwards; it then passed 4 of 4 on its own. The whole script was not run again after that last fix.

What changed for the flows that failed before:

- **Document answer.** The prompt shows each passage of an attached document after its anchor and tells the model to cite it. An anchor the answer repeats becomes a citation part, so the chat draws a source chip. The model still chooses whether to cite.
- **Structured output.** The model is told the schema the caller asked for. A reply that misses it is sent back with the schema. One that still misses it ends the run `failed`; it is not stored as the answer.
- **Approval.** The flow now makes an agent and a policy that need approval. The run pauses, nothing is written, the agent's owner is refused when they try to approve, and a second person's approval lets the write run. This found that an approved call never ran in production mode, which is fixed.
- **External API.** A bad key now gets 401. With no tenant opened, the route answered 404 before it checked the key.
- **Read a number from an image.** The model called `image.ask`, which needs a vision model, and stopped at its refusal. The refusal now says the text in an image can still be read with `documents.ocr`.
- **CSV to chart.** The earlier HTTP 500 was a Valkey timeout while the unit suite ran on the same machine. It did not recur. The product turning that timeout into 500 is still listed below.

The approval flow signs in a second person from `AR_CERT_APPROVER_EMAIL` and `AR_CERT_APPROVER_PASSWORD`. Without them it reports that it needs a second person and does not pass.

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
| Files exported from a computer kept their bytes in process memory | The file row was saved and its download returned 404: exports, screenshots and saved PDFs | The bytes go to the object store before the row is stored |
| The image's browser step removed the data libraries, and a login shell reset `PATH` | `import pandas` failed in every command in the container | The browser sync is inexact, the image puts its environment first for login shells, and the build fails if the libraries do not import |
| A table query naming a quoted file path returned the engine's own error | "file system operations are disabled by configuration", which the model read as a broken tool | The refusal names the tables |
| What a run waited on for approval was held in process memory | After approval the run stayed paused for ever | It is kept on the run's stored checkpoint |
| The approved call was sent to the tool gateway before the decision was committed | The gateway saw a pending approval and refused the call | A step for another process runs after the request's commit |
| A caller's `responseFormat` was never shown to the model, and a miss was stored as the answer | A tool-call-shaped object came back as the answer | The schema is in the prompt and in the retry; a miss ends the run `failed` |
| An external route looked up its store before checking the key | A bad or missing key got 404 in production mode | It gets 401 |
| An attached passage was shown without its anchor, and a cited anchor made no citation part | No source chip for an answer from an attachment | Passages carry anchors and a cited one becomes a citation part |
| The vision tool's refusal spoke only to an administrator | The model stopped and did not read the text another way | The refusal names `documents.ocr` |
| A browser click with no element waited 30 seconds | The model got a timeout it could not act on | It is refused at once: "ref is required: take it from the last browser.snapshot" |
| A console tool test with no conversation crashed | HTTP 500 for `sandbox.exec` | The event carries an empty conversation id |
| Console tool tests could not share a folder | Each test ran in an empty folder | The test body takes `conversationId` |

## Open defects

Ordered by how much they block production.

1. **Research matches by words, not meaning.** A passage counts when it shares a distinctive word with the question. The report quotes the first sentence of each source and is not written by the model. A question phrased differently from the document can miss it. *(Update 2026-11-12: retrieval now also ranks by meaning through the `embed` alias, merged with the word match (`research.minScore`, default 0.3); see [OQ-130](../../open-questions.md). Still open: passages are embedded per query up to a cap, so a large library wants embeddings stored at ingest, and the report stays extractive, not model-written.)*
2. **A computer is proven on one machine only.** The docker driver works in production mode. No computer has run on a cluster: the Kubernetes driver now takes its image from `AR_SANDBOX_IMAGE`, the same setting as the docker driver, but that is covered by unit tests only and the chart change was not rendered here. Suspend does not stop a container, and the docker driver does not confine the network ([OQ-132](../../open-questions.md)).
3. **A Valkey timeout on the session read returns HTTP 500.** It should be a retry or 503 with words. *(Fixed 2026-11-12: the session read runs inside `AuthenticateMiddleware`, where a raised error escaped the problem-details handler and reached the ASGI server as a bare 500. The middleware now catches the loader's `ArError` and answers with its own status — 503 `unavailable` with words — so the caller can retry.)*
4. **Stored rows that are filled in after assignment.** Nine sites are fixed. The tracked store copies a row on assignment, so any other code that keeps writing to its own dict loses those writes in production. The tree has not been swept for every case. *(Update 2026-11-12: `libs/ar_domain` swept; the three remaining live sites are fixed with `keep` — the subagent run (`skills/delegate._insert_child`, which lost the child's final status, result and usage), the knowledge source first sync (`knowledge/book.create_source`, which lost the cursor and sync status), and the policy create row (`policy/service.create`) — each with a regression test that runs under tracking. Two latent gaps found and recorded in [OQ-135](../../open-questions.md): `ingestion_jobs` is not a tracked bucket, and `TrackedDict` has no `setdefault`.)*
5. **Process-memory writes of file bytes.** `sandboxes/service.py` and `identity/data_rights.py` write bytes into process memory. In production those bytes are gone after the request. The sandbox artifact path in `sandboxes/runtime.py` is fixed. *(Fixed 2026-11-12: both now store the bytes through the object store via `files/objects.keep_bytes` — the data export is a durable `files` row of kind `export`, and the showcase chart carries an `object_key` — so a read goes to the store, proven by clearing the in-process cache and reading the bytes back. Note: `data_rights.export_user` still has no download endpoint — a pre-existing gap, now unblocked since the bytes are durable — and `sandboxes/service.seed_chart` runs only from the showcase builder, not a production request.)*
6. **A run that waits on a person resumes in the API process.** `resume`, `resume_answer` and the task that continues a run after an answer are process memory. The approval path now works because it finishes inside the deciding request, but the Temporal resume the spec describes is not built: the approval wait workflow is never started, and the model writes no reply after an approved call ([OQ-133](../../open-questions.md)).
7. **The tenant seed run by hand in staging mode stops with an error** after it creates the people, unless a flag that only the chart's job sets is present. *(Fixed 2026-11-12: `bootstrap.provision_defaults` is the declared bootstrap writer, so it sets `AR_BOOTSTRAP_WRITER` around its own durable write and restores it afterwards. A by-hand `scripts/seed_tenant.py` in staging now writes the default agents without the operator knowing the flag; the Helm job's setting is redundant but harmless.)*
8. **Answers from an attachment are cited only when the model repeats an anchor.** Nothing forces it to.
9. **Deleting the last file in a turn does not stick.** The next turn restores the folder from an earlier run that still had the file. *(Fixed 2026-11-12: a run that had files and then ends with none keeps a tombstone (an empty-path `workspace_files` row), and `_prior_run` treats the tombstoned run as the conversation's latest workspace state, so the next turn restores its zero files instead of falling back to an older run. A turn that never had files writes no tombstone, so it still inherits earlier work.)*
10. **The tool detail API shows parameter names in camelCase.** The tools require snake_case names such as `file_id`. The Tools screen shows names that do not work. *(Fixed 2026-11-12: the global response camelizer recursively renamed every key, including a tool's `input_schema.properties` keys, which are parameter names the tool accepts. `input_schema` and `output_schema` are now opaque in `ar_common.json_api` — the field name is camelCase but the JSON Schema inside is copied through unchanged, so the screen shows the names the tool takes. Fix is API-side; the web shows what the API returns.)*
11. **Built-in tool text is not updated for stored tenants.** Approved tool versions cannot change, so a release that changes a built-in tool's description or schema reaches a stored tenant only in memory.
12. **A refused boot is logged as "temporal_unavailable"** with no message, and retried for ever. *(Fixed 2026-11-12: the three workers (runtime, system, ingest) log through a shared `temporal_unavailable_fields` helper that names the address they tried, the error detail and the retry interval, so an operator can act. The reconnect loop stays — a worker should keep its health server up and retry a transient Temporal outage — but it is no longer silent.)*
13. **The data connection body defaults its address to `memory://warehouse`.** *(Fixed 2026-11-12: `DataConnections.create` no longer defaults the dsn — a connection without one is refused with "a dsn is required: the address of the warehouse" instead of silently becoming the fake in-memory warehouse. An explicit `memory://` dsn is still accepted for the dev and test fixture.)*
14. **A knowledge document created through the collection reads back as "pending"** in listings even after it is indexed, where the code path was not one of the nine fixed.
15. **Every request loads every message of the tenant.** `hydrate_tenant` reads all messages, runs and events per request. This will not hold at production size.
16. **In dev mode a turn longer than about a minute shows as stuck.** The API's watcher stops polling and the message stays "streaming". Dev only, but it is the mode the team uses.

## Local CI run

The CI jobs were run by hand on this branch on 12 November 2026, on one Mac.

| Job | Result |
|---|---|
| Python lint: format, lint, full typecheck, import rules, dependency check | pass |
| Domain-agnostic check | pass |
| Unit tests with the coverage gate | pass: 1,402 tests, coverage 85.06% against a required 85% |
| Contract eval | pass |
| Integration tests | pass: 38, with 2 skipped |
| Tool matrices and the document toolchain | pass |
| Web: lint, typecheck, unit tests, unused-code check, production build | pass |
| Generated code drift (`make gen`, then no diff) | pass |
| Policy tests (`opa fmt`, `check`, `test`) | pass, with OPA run from its container image |
| Migrations: upgrade, check, downgrade to base, upgrade | pass on a fresh Postgres |
| Qdrant conformance | pass, with a Qdrant container |
| Docs checks | pass, except the stack pin check: this Mac has `uv` 0.13.4 and the pin is 0.13.3 |
| Web end to end | see below |
| Helm, the three kind jobs | not run: Helm and kind are not installed here |
| Compose smoke, fresh clone | not run |
| Security: gitleaks, pip-audit | not run: neither tool is installed here |

What the run found and fixed:

- **Coverage was 84.8%.** The container paths of the sandbox tools, the pod launch path, the manager's routes and approval settlement had been proven live only. They now have unit tests.
- **The research end-to-end test relied on the fixture this branch removed.** It uploads its own notes now.
- **A scrollable block in the tool card could not be reached by keyboard.** The accessibility check failed on the computer spec. It fails on `main` too.
- **The standalone web start script never listened on localhost.** It read the listen address from `HOSTNAME`, which the shell sets to the machine's name.

Four unit tests that fail in a plain local run are not defects. Two need a Qdrant server and pass with one. One needs the `opa` program and passes with it. One reads a port from a local `.env` file; CI has none.

**Web end to end could not be made to match CI on this machine.** CI runs it on the dev server with no `.env` file and two retries. Here the dev server times out compiling pages on first visit, and the production build picks up local `.env` values: a shared policy server that learns a new policy late, and an API port the standalone server cannot find. So the same suite was run in the same local mode on both: the production build, with `.env`, two retries.

| | Passed | Failed | Flaky |
|---|---|---|---|
| `main` | 61 | 3 | 1 |
| This branch | 62 | 2 | 1 |

The two that fail on the branch, the policy spec and the widget spec, fail on `main` in this mode too, for the two local causes above. The widget spec passes 5 of 5 on a clean dev server, and both pass when the `.env` file is moved aside. The third failure on `main` is the accessibility defect this branch fixes. CI is the judge for this job.

The Helm chart change for the sandbox image has not been rendered anywhere yet.

## Using the app as a person

On 12 November 2026 the app was used in a browser on the staging-mode stack, signed in as the tenant admin, with the real model and a real sandbox container.

| Step | Result | Time |
|---|---|---|
| Sign in | works | at once |
| A plain question | a sensible answer with follow-up prompts | about 10 seconds |
| A bar chart from numbers typed into the message | chart drawn with the right names and values | 50 to 80 seconds |
| Python with numpy for a mean and standard deviation | right numbers, run in a sandbox container | about 60 seconds |
| Research on a question the document library answers | right answer with a verified citation | about 30 seconds |

Attaching a file was not tested this way; the scripted flows cover it.

The scripted checks had passed on all of this. Using the screen found what they do not look at, and each is fixed:

| What a person saw | Cause | Now |
|---|---|---|
| The chart's axis read 0, 1, 2, 3 | The model wrote rows as `{"North": 12}` and the tool took the key for a column | The key is the label |
| The tallest bar's value was drawn over its name | No room above a bar that reaches the top | It is drawn inside the bar |
| The plan stayed "In progress" after the answer | Nothing settled the steps the runtime writes for tool calls | They are marked done, or cancelled on failure, and cleared when the next turn starts |
| A blank reply for up to a minute | No state was shown before the first text or tool | "Working on it…" |
| The research report said the same sentence twice and printed internal addresses | Two copies of one document matched; the report printed each source's address | One source per text, named by title |
| A panel titled "Sources" listed the questions | Wrong heading | Headed "Research", with the source count and the questions searched |
| The page scrolled into an empty area | Screen-reader labels in the message list were placed against the page | The list contains them |
| The assistant said it could search the web and answer questions about images | Both tools were offered with no provider and no vision model set | A tool the tenant has not set up is not offered to the model |
| The agent picker listed archived agents | The picker took every agent | Archived agents are left out |

One effect to know: on this install the assistant now has 30 tools, not 32, which is at the threshold and no longer over it. It is offered all 30 on each turn instead of a searched subset.

Still visible and not fixed: the model sometimes writes sums between dollar signs, which the chat shows as plain text; and at a narrow window width the chat column is squeezed between the conversation list and the computer panel.

## What is needed to finish

| Need | Unblocks |
|---|---|
| A page with a form on an allowed host, and a stored browser sign-in | 5 browser tools |
| A web search provider and key | Web results in research, `general.search` |
| Hosts for web access on the allowed list | `general.fetch`, `general.http` |
| A vision model on the `vision` alias | `image.ask` |
| The Helm, kind, compose and security CI jobs, which need tools this Mac lacks | A pull request with every job proven |
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
  AR_CERT_APPROVER_EMAIL=... AR_CERT_APPROVER_PASSWORD=... \
  uv run --no-sync python scripts/tool_certification.py --repeat 2 --out var/tool-certification
```

`honcho` reads `.env` again and overrides the shell, so the staging values must be in the environment file it is given (`honcho start -e <file>`).

The run writes `tools.json` and `flows.json`. Exit code 1 means a case failed, a flow failed or was flaky, or a built-in tool has no case.
