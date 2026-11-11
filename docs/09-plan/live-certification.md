# Live certification

Proof label: `live` only when this run used the tenant's model. The report names the model id and the date. A run without `AR_LLM_API_KEY` writes a scorecard labelled `contract` and leaves the live run pending. It does not invent a model id.

The kind job (`scripts/stage9_kind_contract.sh`) is `contract`. It installs the chart with 2 API replicas and 2 workers and uses fake-llm.

## Ports

The owner's Postgres is on host port **5433**. Do not bind 5432, 6379, 7233, 8000 or 8013. The script exits if a URL uses one of those ports.

The API listens on `AR_API_PORT` when that is set, otherwise `AR_PORT` (default 8000). `AR_API_URL` is the origin the certification calls. When it is unset, the script uses `http://127.0.0.1:$AR_API_PORT` (or `$AR_PORT`). The Procfile starts `ar-api`, which binds that port. The web dev proxy (`apps/web/dev-env.ts`) sends `/api` and `/v1` to `AR_API_URL`, or to `127.0.0.1:$AR_API_PORT` when only the port is set. mcp-sql owns host port 8010, so a certification that cannot use 8000 sets `AR_API_PORT` (for example 18010) rather than taking 8010.

| Service | Host port |
|---|---|
| Postgres | 5433 |
| Valkey | 6380 |
| Temporal | 7234 |
| API | `AR_API_PORT` or `AR_PORT` (8000) |
| Web | 3000 |
| mcp-gateway | 8002 |
| sandbox-manager | 8003 |
| system worker | 8014 |

## Command

From a checkout, with the stack already up and a real document on disk:

```bash
export AR_DATABASE_URL=postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5433/agentic_runtime
export AR_VALKEY_URL=redis://127.0.0.1:6380/0
export AR_TEMPORAL_ADDRESS=127.0.0.1:7234
export AR_API_PORT=18010          # omit to use AR_PORT (8000). Do not use 8010 (mcp-sql).
export AR_API_URL=http://127.0.0.1:${AR_API_PORT}
export AR_PUBLIC_URL=http://127.0.0.1:3000   # the browser opens this origin
export AR_WEB_URL=http://127.0.0.1:3000       # used only when AR_PUBLIC_URL is unset
export AR_LLM_BASE_URL=https://api.deepinfra.com/v1/openai
export AR_LLM_MODEL=Qwen/Qwen3-32B
export AR_EMBED_MODEL=Qwen/Qwen3-Embedding-8B   # DeepInfra also serves BAAI/bge-m3
export AR_EVAL_MIN_PASS_RATE=1     # live eval fails below this, and when every case errored
export AR_LLM_API_KEY=...          # never commit this
export AR_ADMIN_EMAIL=admin@dev.local
export AR_ADMIN_PASSWORD=...
export AR_SECOND_EMAIL=reviewer@dev.local
export AR_SECOND_PASSWORD=...
export AR_SECOND_NAME="Cert Reviewer"
export AR_SECOND_ROLE=approver
export AR_CERT_DOCUMENT=/path/to/a-real-document.txt
export AR_CERT_OUT=var/live-certification
bash scripts/certify_live.sh
```

The scorecard is `var/live-certification/scorecard.json`. Playwright screenshots are `var/live-certification/screenshots/`. Both name the model id and the date when the label is `live`.

Sign-in uses `scripts/sign_in.py`, which keeps `ar_session` and `ar_csrf`. Every mutating session call sends `X-CSRF-Token`. The CSRF middleware is unchanged.

Seed the second person with the tenant instead of inserting a row by hand:

```bash
export AR_SECOND_EMAIL=reviewer@dev.local
export AR_SECOND_PASSWORD=...
export AR_SECOND_ROLE=approver
uv run python scripts/seed_tenant.py --slug cert --name Cert \
  --admin-email admin@dev.local --admin-name "Cert Admin"
```

`AR_SECOND_PASSWORD` is required when `AR_SECOND_EMAIL` is set. The role key defaults to `approver`.

The run registers the chat model and an embedding model. The embedding default is `Qwen/Qwen3-Embedding-8B` (`AR_EMBED_MODEL`), which DeepInfra serves at `{AR_LLM_BASE_URL}/embeddings`, with `embeddingDimensions` 1024. `BAAI/bge-m3` is the other model DeepInfra serves for the same API. Aliases `chat`, `reasoning`, `fast` and `vision` point at the chat model. `embed` points at the embedding model. Retrieval fails with `embedding_unconfigured` when `embed` is missing; it does not pretend the library was empty.

There is no `/audit` page. Screenshots cover `/login`, home, `/agents/new`, `/documents` and `/approvals`. The audit proof is `GET /api/v1/audit-events` and `scripts/verify_audit_chain.py --tenant <uuid>`. The browser opens `AR_PUBLIC_URL` (falling back to `AR_WEB_URL`). After sign-in, a shot that is still `/login` fails the screenshots step. Dev and CI treat `localhost`, `127.0.0.1` and `::1` as the same CSRF origin; production does not. Extra origins go in `AR_CSRF_ALLOWED_ORIGINS`.

Each step has `result`: `pass`, `fail`, `skipped-no-token` or `unverified`. A connector, OCR or mail step with no token is `skipped-no-token` and does not block `live`. `unverified` and `fail` do. `label` is `live` only when every other step passed. The live eval uses `chat_completions_url` (the same join as the model gateway) and the shared chat-completion body, which always sends a bounded `max_tokens` (`AR_LLM_MAX_TOKENS`, default 1024, or the case's own cap, never above the model limit). A provider error records the HTTP status, a redacted body and the latency. The step fails when `pass_rate` is below `AR_EVAL_MIN_PASS_RATE` or every case errored. Research polls until a terminal status (`AR_RESEARCH_POLL_TIMEOUT_S`, default 180 seconds). `outcome` is `pass`, `failed` or `timeout`. A tool call's idempotency key is the run, step, query and provider call, and a retry adopts the stored row instead of failing the flush. The assistant message stores `answeredModel`, so a reload still shows which model answered. A chart reply includes the image part, and the Computer pane lists each artifact once.

## What the run does

1. Sign in through the UI and screenshot the home page.
2. Open the agent builder and create an agent.
3. Upload `AR_CERT_DOCUMENT`.
4. Run `documents.judge` with a rule set.
5. Send a chat turn that calls a tool through mcp-gateway.
6. Approve a four-eyes request as the second user.
7. Read the audit chain and run `scripts/verify_audit_chain.py --tenant <uuid>`. There is no audit page to screenshot.
8. Start a research run and poll it until it completes, fails or the timeout (`AR_RESEARCH_POLL_TIMEOUT_S`, default 180s, every `AR_RESEARCH_POLL_INTERVAL_S` seconds, default 2). The report cites stored pages. Each source has `sha256` and `fetchedAt`. A failed run and a run still going at the timeout are recorded separately. This step uses the fixture provider unless a search secret is configured. It does not invent a search-provider result.
9. Run `scripts/eval_run.py --live` against `AR_LLM_BASE_URL` joined with `chat_completions_url`. Each request sends `max_tokens`. The scorecard records the model id, the date, the summary, and per case the status, redacted provider error and latency. The step fails when `pass_rate` is below `AR_EVAL_MIN_PASS_RATE` or every case errored. A missing key leaves the live run pending and the label stays off `live`.
10. Send a chat turn with `researchMode` false and confirm the run trace can include `endpointId` when model routes are configured. No API key is written into the scorecard.
11. Probe each connector whose token is set. A missing token is `skipped-no-token` and does not invent a provider result. A provided token that fails is `fail` and keeps the label off `live`.
    - `AR_CERT_SLACK_TOKEN`, `AR_CERT_GOOGLE_TOKEN`, `AR_CERT_MICROSOFT_TOKEN`, `AR_CERT_ATLASSIAN_TOKEN`, `AR_CERT_GITHUB_TOKEN`
    - `AR_CERT_GDRIVE_TOKEN`, `AR_CERT_GCAL_TOKEN`, `AR_CERT_GMAIL_TOKEN`, `AR_CERT_OUTLOOK_TOKEN`, `AR_CERT_ONEDRIVE_TOKEN`, `AR_CERT_TEAMS_TOKEN`
    - `AR_CERT_JIRA_TOKEN` with `AR_CERT_JIRA_URL`, `AR_CERT_CONFLUENCE_TOKEN` with `AR_CERT_CONFLUENCE_URL`
    - `AR_CERT_REST_TOKEN` with `AR_CERT_REST_URL`
12. When `AR_CERT_OCR_GOOGLE`, `AR_CERT_OCR_AWS` or `AR_CERT_OCR_AZURE` is set, post one page to that named endpoint. Otherwise the OCR step is pending.
13. When `AR_GREENMAIL_SMTP` is set (`host:port`), send one notice through that SMTP server. Otherwise the mail step is pending. The integration job runs GreenMail and does not require this variable.

`fail` and `unverified` keep the scorecard off `live`. `skipped-no-token` does not.
