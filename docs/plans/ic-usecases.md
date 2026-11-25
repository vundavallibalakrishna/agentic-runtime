# IC use cases: platform hardening, extraction, horizon scan, scenario runs

Plan for one pull request. Written against `main` at `138674b8` (24 Nov 2026). Every file and line below was read in this tree. The feasibility notes that prompted the work are input only and are not copied here.

Core stays domain-agnostic. Insurance, internal-audit, and stress-testing content lives under `packs/examples/`. Catalogue rows may name a vendor, the way Slack and Jira already do. No new infrastructure: Docker Compose, the existing system worker, the existing channel service, the existing approval and review paths.

## What is already true

### Approvals leave the console only as text, and two links are fake

- A Slack or Teams button is decided on the same path as the inbox. `decide_approval` maps the external user to a tenant user and calls `ApprovalBook.decide` (`libs/ar_domain/src/ar_domain/channels/service.py` lines 73–110).
- Nothing posts a card. `slack_approval_message` builds Slack blocks and has no caller (`services/channels/src/ar_channels/handlers.py` lines 181–185). `ChannelBook.notify` records a text post only (`libs/ar_domain/src/ar_domain/channels/book.py` lines 236–272). The channels process `/internal/v1/outbound` appends the body to an in-memory outbox and does not call Slack or Teams (`services/channels/src/ar_channels/main.py` lines 99–106). `slack-sdk` is already a dependency of `ar-channels`.
- The Teams card "Open in web" action is the literal `https://localhost/approvals` (`services/channels/src/ar_channels/render.py` lines 79–81). `approval_blocks` already takes a `web_url` argument (line 41).
- The approval email recipient is the literal `approvals@dev.local` (`services/system/src/ar_system/workflows/notification_fanout.py` lines 41–49). Approver ids are already resolved from the rule (`requester`, `users`, `group`, `agent_owner`) in `ApprovalBook._approver_ids` (`libs/ar_domain/src/ar_domain/approvals/service.py` lines 568–590) and stored on the `approval.requested` payload (lines 246–255). Emails of users live on `ChatService.user_emails` (`libs/ar_domain/src/ar_domain/chat/service.py` line 480).
- Edit-then-approve keeps both versions: the original row is rejected with comment `edited`, and a new pending row holds the corrected arguments and a new args hash (`libs/ar_domain/src/ar_domain/approvals/service.py` lines 92–94 and 405–454). The decide body already accepts `arguments` (`services/api/src/ar_api/routers/approvals.py`).
- The public origin is `AR_PUBLIC_URL`, default `http://localhost:3000` (`docs/07-ops/environments.md` line 193, `services/api/src/ar_api/main.py`). Signed HMAC tokens already exist for channel linking (`libs/ar_domain/src/ar_domain/channels/tokens.py` lines 31–65).
- There is no single-item review route. Public routes are listed in `services/api/src/ar_api/middleware/stack.py` lines 11–45 and `services/api/src/ar_api/auth/route_access.py`.

### Tenant webhooks are specified and stored, and not delivered

- Tables `outbound_webhooks` and `webhook_deliveries` exist, with RLS, from migration `0004` (`libs/ar_domain/src/ar_domain/events/models.py` lines 65–120, `docs/04-data/schema.md` lines 1400–1431). The signing helper and the backoff schedule exist (`libs/ar_domain/src/ar_domain/events/sign.py` lines 8–21). Routine deliveries already POST with `X-AR-Signature` via `sign_body` (`libs/ar_domain/src/ar_domain/routines/outbound.py` lines 101–120). Run callbacks sign with `sign_run_callback` (`libs/ar_domain/src/ar_domain/runs/callbacks.py` lines 54–66).
- The API does not use those tables. `app.state.webhooks` is the in-memory `WebhookApi` (`services/api/src/ar_api/state.py` lines 127–187, `services/api/src/ar_api/main.py` line 436). `redeliver` discards the id (line 187). CRUD is `services/api/src/ar_api/routers/webhooks.py` lines 22–113.
- Public topics already include `approval.requested`, `approval.decided`, `run.completed` and `run.failed` (`libs/ar_contracts/src/ar_contracts/events.py` lines 31–57). There is no `document.ingested` topic and no extraction topic. `NotificationFanoutWorkflow` is not registered on the system worker (`services/system/src/ar_system/worker.py` lines 86–107). The spec already names `WebhookDeliveryWorkflow` on queue `ar-system` (`docs/03-specs/20-notifications-events.md` lines 3 and 93–94). That workflow class does not exist in code.

### Extraction is one prompt and all-or-nothing

- `DocumentLibrary.extract` sends every passage in one prompt, validates the whole object, and raises if validation fails (`libs/ar_domain/src/ar_domain/documents/library.py` lines 675–714). Nothing is stored. The tool entry is `libs/ar_domain/src/ar_domain/tools/documents.py` lines 121–131.
- A quote can be checked against stored text: `ar_domain.documents.grounding._contains` (`libs/ar_domain/src/ar_domain/documents/grounding.py`). A layout miss is recorded as `metadata.parser = "fallback"` and `parserNote` (`libs/ar_domain/src/ar_domain/documents/layout.py` lines 57–62) and is not raised as a review.
- Whether text fits a model is already measured. `estimate_tokens` and `usable_tokens` compare a token count with the registered context window (`libs/ar_domain/src/ar_domain/documents/strategy.py` lines 31–69). `context_window_for` reads the run's model (`libs/ar_domain/src/ar_domain/documents/binding.py` lines 94–102). There is no keyword routing.
- Eval assertions are a closed `if` in `_one` (`libs/ar_domain/src/ar_domain/evals/scoring.py` lines 86–120). There is no per-field comparison. Suites are YAML and the CLI is `scripts/run_suites.py`.
- `.msg` is sent through LibreOffice to text (`libs/ar_domain/src/ar_domain/documents/convert.py` lines 43–44 and 48–49). The ingest image has LibreOffice (`images/ingest/Dockerfile`). The API image does not. `services/ingest/pyproject.toml` does not declare SQLAlchemy or an Outlook parser. A search of `services/ingest` finds no `sqlalchemy` import, so the DEP003 finding is not present in this tree; the ingest activity will declare only what it imports.
- Library uploads are parsed on the ingest worker (`services/ingest/src/ar_ingest/activities.py` `parse_library_activity`, around lines 90–124).

### Horizon scanning and routines

- `packs/examples/policy-watch` is a content pack: skill, agent, paused routine, `web.discover`, conditional ingest, `documents.diff`, deliveries (`packs/examples/policy-watch/build_manifest.py`). Its agent budget is 40 steps and 60 tool calls (lines 15–22), larger than the platform default.
- The platform run budget is the constant `DEFAULT_RUN_BUDGET` (16 steps, 16 tool calls, 80_000 tokens) in `libs/ar_domain/src/ar_domain/runs/logic.py`. Migration `0063` rewrote routines that still held the old 8-step / 4-tool default. The numbers are not settings.
- Skill publish does not validate a JSON Schema for a settings document. Pack import applies `Agent`, `Skill` and `Routine`, and skips `Policy` (`docs/open-questions.md` OQ-175).
- `extension_rows` is the generic pack record store (`libs/ar_domain/src/ar_domain/durable/tables.py`). Tools whose names start with `records.` are omitted from the capability matrix because that prefix belonged to the retired records product (`libs/ar_domain/src/ar_domain/proof.py`).
- Connector auth kinds are `api_key`, `bearer`, `basic`, `oauth_authorization_code`, `oauth_client_credentials` (`libs/ar_domain/src/ar_domain/tools/service_connections.py`). There is no `token_exchange`. `ConnectorDef` already has `token_url` (`libs/ar_domain/src/ar_domain/connectors/catalog.py` lines 47–73). Catalogue rows are assembled from `catalog.py`, `catalog_batch.py` and `catalog_stage11.py`.

### Sandbox

- `general.code` and `general.shell` run in the conversation computer and publish new files with a SHA-256 (`libs/ar_domain/src/ar_domain/tools/general.py`). There is no tool that runs a registered file at a fixed entry point and returns hashes of the script, the params and the outputs.
- The sandbox image installs LibreOffice (`images/sandbox/Dockerfile`). Headless recalculation of a workbook is not covered by a test in this tree, so this PR does not claim it.

## Story 1 — Platform hardening

### 1a. Post the card

When `ApprovalBook.create_pending` has stored the row, and the tenant has a Slack or Teams integration or an approver has a linked identity on one, `ChannelBook` records an outbound post whose detail is an interactive card: Approve, Reject, and a review link. The channels process is the sender. `/internal/v1/outbound` calls `slack_approval_message` for Slack and `adaptive_card` for Teams, then, when the integration's stored credential has a bot token or an incoming webhook URL, POSTs the card with `slack-sdk` or `httpx`. With no credential the card is still recorded and the result says the credential is absent. That path is not live-tested against a customer tenant.

A step-up approval sends only the review link, which is the behaviour `approval_blocks` already has.

### 1b. Real recipients and a real origin

`notices_for` stops using `approvals@dev.local`. The fan-out activity resolves `approver_user_ids` through `user_emails`. A missing address is skipped. `AR_APPROVAL_NOTIFY_EMAIL` is an optional extra recipient for installs that want a shared mailbox; empty means no extra recipient.

The card and the mail use `{AR_PUBLIC_URL}/review/{token}`. `render.adaptive_card` takes that URL from the caller. The localhost literal is removed.

### 1c. One-item review page

`ar_domain.approvals.review_link` issues an HMAC token (same construction as channel link tokens) naming the approval, the tenant and one approver, expiring with the approval (`AR_REVIEW_LINK_TTL_S`, default the approval TTL). Each approver gets their own link.

`GET /api/v1/review/{token}` returns the pending approval: tool name, arguments, the tool's input JSON Schema when the catalogue has one, and the preview. It does not return other approvals.

`POST /api/v1/review/{token}:decide` calls `ApprovalBook.decide` as that approver, with `channel="review_link"`. A body that contains `arguments` uses the existing edit-then-approve path, so the original and the edited arguments are both kept. A reason is the comment.

When the tenant has an OIDC provider configured, the token only names the item. The caller must have a session for that tenant whose user is the approver named in the token. When no provider is configured, the signed token is the credential and the decision is attributed to the named approver. Guests are not approvers.

The page is `apps/web/src/app/review/[token]/page.tsx`. It renders any object schema: string, number, integer, boolean, and arrays of those. No domain fields. Loading, empty, expired and error states are present. Colours come from the tokens in `apps/web/src/app/globals.css`. The card and the email include the link.

### 1d. Deliver the webhooks that are already specified

`WebhookApi` becomes a facade over a domain book that reads and writes `outbound_webhooks` and `webhook_deliveries` (memory on `ChatService` for the request, flushed with the other durable rows). The signing secret is a named secret, returned once on create and on rotate, and is not in the public row. Topics must be public topics.

`dispatch_public_event(store, topic, payload)` inserts one delivery per active subscription of that tenant whose topics include the event. It is called for `approval.requested`, `approval.decided`, `run.completed`, `run.failed`, and for two new public topics: `document.ingested` (library ingest finished) and `extraction.completed` (an extraction was stored). Payload is ids and status, not document text.

`WebhookDeliveryWorkflow` is registered on the existing system worker. Its activity POSTs the camelCase envelope with `X-AR-Signature` from `sign_body`, `X-AR-Event-Id` and `X-AR-Topic`, timeout 10 seconds, through the egress client. Backoff is the existing `BACKOFF_S`. After the schedule is exhausted the delivery is `dead`. Replay (`:redeliver`) inserts a new attempt of the same event. A process without Temporal runs the same activity function, the way run callbacks already deliver on a thread. No new broker.

## Story 2 — Extraction

### 2a and 2b. Per-field results, chosen from the measurement

`DocumentLibrary.extract` keeps its signature. The return gains `fields` and `strategy` and no longer raises because a required field is absent.

Each leaf field is `{value, quote, page, locator, confidence, quote_verified, status}`. `confidence` is the number the model reported. `quote_verified` is `grounding._contains` against the passage text. `status` is `extracted` (quote verified and confidence at least `AR_EXTRACTION_MIN_CONFIDENCE`, default 0.8), `low_confidence` (quote verified, below the threshold), `missing` (required by the schema and absent, or a quote that is not in the source), or `conflicting` (two chunks produced different verified values). Threshold and the token margin come from settings, not from code. Required fields come from the schema's `required` arrays, walked for nested objects.

Strategy: `estimate_tokens` of the passage text against `usable_tokens(context_window)`. When the text fits, one call. When it does not, passages are split into chunks that fit and each chunk is extracted, then merged. A missing window uses `AR_DEFAULT_CONTEXT_WINDOW` only as the measurement the strategy module already uses; it does not invent a keyword rule. The model still fills the schema. The code only measures, splits, verifies quotes and merges.

`result` is the partial value object (present leaves only). Callers no longer need every required field to succeed.

### 2c. History

Migration `0064` adds `document_extractions`: tenant, document, content hash, schema hash, model alias, strategy, fields, corrections, approval id, run id, created at. RLS and grants in the same revision. The memory store and the flush path match the other document tables. `GET /api/v1/library-documents/{document_id}/extractions` lists them. The write is audited as `extraction.recorded`.

### 2d. Exceptions use approvals

When any field is `missing`, `low_confidence` or `conflicting`, or the document's `parser` is `fallback`, the tool handler raises one pending approval through `ApprovalBook.create_pending`. The qualified name is `documents.review_extraction`. The arguments are the field values. The preview carries the schema, the per-field evidence and the parser note. The review page from story 1 renders that schema. No new queue type.

### 2e. `fields_match`

A new assertion type in `_one`, implemented in `ar_domain.evals.fields`. It compares a JSON object in the output with `expected`. Per field it reports exact match and a normalised match. Normalisers are named on the assertion (`exact`, `date`, `number`, `name`) and are functions, not a keyword list about the document. The score detail is precision, recall and F1 over the labelled leaves, plus a per-field breakdown. `document_type` on the assertion is a label the report groups by. The existing eval API and `scripts/run_suites.py` run it because they already call `grade`.

### 2f. Outlook `.msg` on the ingest worker

`extract-msg` is declared on `ar-ingest` only. The ingest activity, before `finish_parse`, parses a `.msg`: headers, body, and each attachment ingested as its own library document (a nested `.msg` goes through the same activity). `convert_and_extract` no longer sends `.msg` to LibreOffice. A parse that runs in the API process raises a clear error that the ingest worker reads this format. If `deptry` reports SQLAlchemy undeclared in `ar-ingest`, it is added; it is not imported there today.

### 2g. Pack `packs/examples/document-extraction`

Content pack, same shape as policy-watch. Two example schemas: an internal review report (report details, findings, recommendations, owners, target dates) and a risk-transfer document (parties, dates, amounts, conditions). Both are pack content. The agent extracts, and on an exception the core path already opens the review approval. The write into a target system is a connector or imported API tool named in the pack settings; the pack ships a policy document the installer activates (`require_approval`, group from settings) because pack import still skips `Policy` (OQ-175). A labelled-set file and an eval suite use `fields_match`. Sample documents are synthetic and say so in the README and in the file header. They are for tests and docs.

## Story 3 — Horizon scan

### 3a. Settings that validate, and the pack

Generic core: `resource_settings` (migration `0065`). A row is a version of a JSON document plus the schema it was checked against, for a resource type and id (`agent` or `pack`). `PUT` validates with Draft 2020-12 and appends a version. The change is audited as `resource_settings.updated`. Endpoints:

- `GET /api/v1/resource-settings/{resource_type}/{resource_id}`
- `PUT /api/v1/resource-settings/{resource_type}/{resource_id}`
- `GET /api/v1/resource-settings/{resource_type}/{resource_id}/versions`

Pack install copies an agent's `settingsSchema` and `settings` into the first version.

`packs/examples/horizon-scan` is a content pack. Settings (schema-checked): sources (feeds, pages, search topics), categories, relevance criteria written as prose, review frequency. The agent scans with the tools policy-watch already uses, scores relevance with reasons and links, dedupes by URL and content hash against earlier rows, and writes candidate rows through `extensions.put` (below). Suggested links to an external register are ids returned by a connector or imported API tool named in settings. The register is not a core table. Writing to that system is a gated tool: the pack's policy document requires approval by the group named in settings. The decision is the review page and the cards from story 1. Digests go out through routines (email, Teams, webhook) with `something_to_report`.

`extensions.put`, `extensions.get` and `extensions.list` are generic tools over `extension_rows` (pack id, bucket, payload). They are not named `records.*`.

### 3b. Vendor feed connector

Auth kind `token_exchange` on service connections: POST the stored secret to the connector's `token_url`, cache the token until the response's expiry (default 24 hours), never place the secret on a query string. Header name and prefix are fields of the catalogue row, not branches in the dispatcher.

The first row is LexisNexis Regulatory Compliance in a new catalogue module included from `CONNECTORS`. Host `https://rcapi-plus.lexis.com`. Token `POST /f/Access/authtoken`. Tools for subscriptions, subscribed contents (including the vendor's `type` and `from_date` query parameters), one content item, mandates, regulators, and document download. `verification` is `not_live`. The note says the paths come from the vendor's published guide and that no call was made with a customer credential.

### 3c. Routine budget from settings

`configured_run_budget()` reads `AR_ROUTINE_DEFAULT_MAX_STEPS`, `AR_ROUTINE_DEFAULT_MAX_TOOL_CALLS`, `AR_ROUTINE_DEFAULT_MAX_TOKENS`, `AR_ROUTINE_DEFAULT_MAX_COST_MICROS` and `AR_ROUTINE_DEFAULT_MAX_WALL_CLOCK_S`. Defaults are the current `DEFAULT_RUN_BUDGET` (16 / 16 / 80000 / 4000000 / 600), which migration `0063` already wrote onto old rows. A routine or agent that sets its own budget still wins, as the ceiling logic does today. Policy-watch keeps its larger budget in the pack.

## Story 4 — Scenario runs

The platform does not interpret results. It stores versions, runs a program, and records hashes.

Only this pack needs "run a registered script and record hashes". Example packs are content: the runtime does not load Python from `packs/examples/` (OQ-176). A tool the agent can call therefore lives in core, with no domain words. `workspace.run_entry` copies the named files into the existing sandbox, writes `params.json`, and runs the entry point from `AR_REGISTERED_SCRIPT_ENTRY` (default `python model.py --params params.json`). The model does not choose the command. The tool returns the exit code, the stdout and stderr text, and the SHA-256 of the script, the params, each input and each output file, plus the command that ran. It does not parse numbers out of the output.

`extensions.compare` computes a field-by-field delta of two JSON objects in code.

`packs/examples/scenario-runs` holds versioned scenario rows (assumptions, and a reason on each new version), model registrations (file id and hash), and run rows (scenario version, model hash, input hashes, output hashes, trace). The agent instructions say to copy numbers only from a run's stored output. Approvals, using the existing machinery and a policy document in the pack:

- scenario agreed, as a multi-level review item
- results approved, four-eyes, and the preparer is not an approver (existing separation of duties)
- report issued, as an approval on `documents.create`

The report is `documents.create`. A tiny Python program under the pack's `examples/` directory prints a fixed JSON object. Tests only. The README says it is synthetic. LibreOffice headless recalculation is documented as not supported until a test shows `soffice --headless` recalculating a workbook in the sandbox image.

## Acceptance

- `apps/web/AGENTS.md` is untouched.
- New tests: unit and integration for each story; a Playwright test of the review page; a webhook delivery test that checks the HMAC; extraction tests on fixture PDFs including one scanned page; `fields_match` tests; a scenario re-run that yields the same hashes.
- Docs: new endpoints in the API catalogue and the owning spec, pack READMEs, and a short guide for calling an agent without opening the console.
- The PR description lists what was exercised here and what needs a customer credential or a real model.

## Decisions applied

| Question | Default applied |
|---|---|
| Where do webhook rows live? | The existing `outbound_webhooks` and `webhook_deliveries` tables. No second store. |
| Who may open a review link? | The approver named in the token. An OIDC tenant also requires that user's session. |
| What does a partial extraction return? | `result` plus `fields`. A missing required field is `status: missing`, not an error. |
| Where does the script runner live? | Core, as `workspace.run_entry`, because a content pack cannot register a Python tool. No domain vocabulary. |
| Is LibreOffice recalculation in? | No. Not verified. The pack says so. |
| Is the LexisNexis row live? | No. Catalogue only, labelled `not_live`. |

## Not in this PR

Customer credentials, a live model run of the packs, Teams or Slack tenants, and actuarial judgement. The platform records what a program printed. It does not produce a capital number of its own.
