# Live certification

Proof label: `live` only when this run used the tenant's model. The report names the model id and the date. A run without `AR_LLM_API_KEY` writes a scorecard labelled `contract` and leaves the live run pending. It does not invent a model id.

## Ports

Compose `--profile production` publishes these host ports. Override a port with the variable in the first column; the in-network address (postgres, valkey, temporal, seaweedfs, otel) does not change.

| Service | Host variable | Default |
|---|---|---|
| Postgres | `AR_PG_HOST_PORT` | 5432 |
| Valkey | `AR_VALKEY_HOST_PORT` | 6379 |
| Temporal | `AR_TEMPORAL_HOST_PORT` | 7233 |
| API | `AR_PORT` | 8000 |
| Web | `AR_WEB_HOST_PORT` | 3000 |
| Model gateway | `AR_MG_PORT` | 8001 |
| mcp-gateway | `AR_MCPG_PORT` | 8002 |
| sandbox-manager | `AR_SANDBOX_MANAGER_HOST_PORT` | 8003 |
| system worker | `AR_SYSTEM_HOST_PORT` | 8013 |
| ingest worker | `AR_INGEST_HOST_PORT` | 8014 |
| S3 (SeaweedFS) | `AR_S3_HOST_PORT` | 8333 |

The API origin is `http://127.0.0.1:$AR_PORT`. The browser origin is `http://127.0.0.1:$AR_WEB_HOST_PORT`. The web process reads `API_PROXY_URL` on each request and proxies `/api`, `/v1` and `/.well-known/agent-card.json` to the API. mcp-sql publishes `AR_MCP_SQL_HOST_PORT` (default 8010); leave the API on 8000.

## Start

From a checkout, with secrets in `.env` (`scripts/dev_keys.py` writes the database passwords):

```bash
docker compose --profile production up -d --build
```

`AR_ENV=staging` is the certification environment. Containers take `AR_S3_ENDPOINT=http://seaweedfs:8333` from `compose.yaml`, so a laptop `.env` that still says localhost does not apply inside a container. Telemetry export is off until `AR_OTEL_EXPORTER_OTLP_ENDPOINT` is set (`http://otel:4317` when the `obs` profile is up).

If port 8000 is already taken, set `AR_PORT` before Compose starts and point the clients at it. The API container listens on that port, OPA polls `http://api:$AR_PORT`, and the web proxy follows it:

```bash
export AR_PORT=28000
export AR_API_URL=http://127.0.0.1:${AR_PORT}
export API_PROXY_URL=http://127.0.0.1:${AR_PORT}
docker compose --profile production up -d --build
```

## One command

`scripts/certify_stack.sh` does everything below on a machine that has Docker and 16 GB of memory: it writes `.env` when there is none, builds the computer image, starts the install in the staging environment with every feature file and the file scanner, seeds one tenant with an admin and a reviewer, starts a computer and runs one command on it through the console's tool test, and runs the parts named in `AR_CERT_PARTS`.

```bash
export AR_LLM_API_KEY=...            # never commit this
export AR_CERT_PARTS="live tools"    # any of: live tools agents; live is required, it connects the model
bash scripts/certify_stack.sh
```

| Variable | Default | Meaning |
|---|---|---|
| `AR_CERT_PARTS` | none | `live` runs `scripts/certify_live.sh`, `tools` runs `scripts/tool_certification.py`, `agents` runs `scripts/agent_certification.py`. With none, the install and the seed are the check |
| `AR_CERT_REPEAT` | 2 | Times each tool flow runs |
| `AR_CERT_EVIDENCE` | `var/certification` | Where the scorecards, each part's log and exit code, the container list, memory use, every service's log and each computer's log are written |
| `AR_CERT_CONTEXT_WINDOW`, `AR_CERT_MAX_OUTPUT_TOKENS` | the product default | The limits the provider serves for the chat model, sent when the run registers it |
| `AR_CERT_POLICY_WAIT_S` | 20 | Seconds the approval flow waits after activating its policy, so a policy engine that polls has read it |
| `AR_CERT_DOCUMENT`, `AR_CERT_RESEARCH_QUESTION` | `docs/00-overview/vision.md` and a question it answers | The document the run uploads and the research question |

The admin and reviewer passwords are generated for the run unless `AR_ADMIN_PASSWORD` and `AR_SECOND_PASSWORD` are set. The script stops with a non-zero exit when a part does not pass, and it leaves the install running so a person can look at it; `docker compose down -v` removes it. An `.env` that is already in the checkout is used as it is and is not rewritten.

The `certification` CI job runs the same script on a hosted runner. Start it from the Actions page (**certification**, **Run workflow**) after adding the provider's key as the repository secret `AR_LLM_API_KEY`. The evidence is the run's `certification-<run id>` artifact, kept for 30 days. The repository is public, so the artifact and the job log are public too; the key and the two passwords are masked, and nothing else in the evidence is a secret.

## Command

With the stack up and a real document on disk. `scripts/certify_live.sh` installs Playwright Chromium into `PLAYWRIGHT_BROWSERS_PATH` (default `.playwright-browsers` in the checkout) so it does not touch a shared browser cache.

```bash
export AR_API_URL=http://127.0.0.1:${AR_PORT:-8000}
export AR_PUBLIC_URL=http://127.0.0.1:${AR_WEB_HOST_PORT:-3000}
export AR_WEB_URL=$AR_PUBLIC_URL
export AR_LLM_BASE_URL=https://api.deepinfra.com/v1/openai
export AR_LLM_MODEL=Qwen/Qwen3.8-27B
export AR_EMBED_MODEL=Qwen/Qwen3-Embedding-8B   # DeepInfra also serves BAAI/bge-m3
export AR_EVAL_MIN_PASS_RATE=0.9   # optional: overrides the certification suite's own pass rate
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

The admin password is `AR_ADMIN_PASSWORD` when that variable is set. Otherwise the script reads one line from stdin, or asks twice on a terminal. `AR_SECOND_PASSWORD` is required when `AR_SECOND_EMAIL` is set. The role key defaults to `approver`.

The approval flow in `scripts/tool_certification.py` signs in as a second person. Set `AR_CERT_APPROVER_EMAIL` and `AR_CERT_APPROVER_PASSWORD` to that person's email and password (the seeded reviewer above). Without them the approval flow is `blocked`, not failed. A flow is `blocked` when it cannot start without something the owner supplies, and a blocked flow does not fail the run. The agent-to-agent flow is blocked when the install's own address is this machine or a private network and `AR_CERT_A2A_URL` names no peer: one install cannot call itself from inside a container.

The run registers the chat model and an embedding model. The embedding default is `Qwen/Qwen3-Embedding-8B` (`AR_EMBED_MODEL`), which DeepInfra serves at `{AR_LLM_BASE_URL}/embeddings`, with `embeddingDimensions` 1024. `BAAI/bge-m3` is the other model DeepInfra serves for the same API. Aliases `chat`, `reasoning`, `fast` and `vision` point at the chat model. `embed` points at the embedding model. Retrieval fails with `embedding_unconfigured` when `embed` is missing; it does not pretend the library was empty.

There is no `/audit` page. Screenshots cover `/login`, home, `/agents/new`, `/documents` and `/approvals`. The audit proof is `GET /api/v1/audit-events` and `scripts/verify_audit_chain.py --tenant <uuid>`. The browser opens `AR_PUBLIC_URL` (falling back to `AR_WEB_URL`). After sign-in, a shot that is still `/login` fails the screenshots step. Dev and CI treat `localhost`, `127.0.0.1` and `::1` as the same CSRF origin; production does not. Extra origins go in `AR_CSRF_ALLOWED_ORIGINS`.

Each step has `result`: `pass`, `fail`, `skipped-no-token` or `unverified`. A connector, OCR or mail step with no token is `skipped-no-token` and does not block `live`. `unverified` and `fail` do. `label` is `live` only when every other step passed. The live eval is an eval run in the product (step 9). It fails when the run does not complete or the suite gate does not pass. Research polls until a terminal status (`AR_RESEARCH_POLL_TIMEOUT_S`, default 180 seconds). `outcome` is `pass`, `failed` or `timeout`. A tool call's idempotency key is the run, step, query and provider call, and a retry adopts the stored row instead of failing the flush. The assistant message stores `answeredModel`, so a reload still shows which model answered. A chart reply passes only when the run called `general.chart` and the reply has an image part. The Computer pane lists each artifact once. Screenshots are taken after the other steps, once each page has finished loading, and `/documents` must list the uploaded document.

## What the run does

1. Sign in through the UI and screenshot the home page.
2. Open the agent builder and create an agent.
3. Upload `AR_CERT_DOCUMENT`.
4. Run `documents.judge` with a rule set.
5. Send a chat turn that calls a tool through mcp-gateway.
6. Approve a four-eyes request as the second user.
7. Read the audit chain and run `scripts/verify_audit_chain.py --tenant <uuid>`. There is no audit page to screenshot.
8. Start a research run and poll it until it completes, fails or the timeout (`AR_RESEARCH_POLL_TIMEOUT_S`, default 180s, every `AR_RESEARCH_POLL_INTERVAL_S` seconds, default 2). The report cites stored pages. Each source has `sha256` and `fetchedAt`. A failed run and a run still going at the timeout are recorded separately. Research searches the tenant's document library, and the web when a search provider is configured. The question is `AR_CERT_RESEARCH_QUESTION`; set it to something the uploaded document answers, so the sources are its passages. A report with no sources says where it looked.
9. Start an eval run in the product from `evals/live/certification.yaml`: create the suite and its cases through `/api/v1/eval-suites`, run it on the published assistant, and poll `/api/v1/eval-runs/{id}` until it ends (`AR_EVAL_POLL_TIMEOUT_S`, default 900 seconds). Each case is a real agent turn with the agent's tools, scored by the suite's assertions. The step passes when the run completes and the suite gate passes. `AR_EVAL_MIN_PASS_RATE` overrides the suite's pass rate. The scorecard records the eval run id, the summary and each case's scores. That product run is the only eval path.
10. Send a chat turn with `researchMode` false and confirm the run trace can include `endpointId` when model routes are configured. No API key is written into the scorecard.
11. Probe each connector whose token is set. A missing token is `skipped-no-token` and does not invent a provider result. A provided token that fails is `fail` and keeps the label off `live`.
    - `AR_CERT_SLACK_TOKEN`, `AR_CERT_GOOGLE_TOKEN`, `AR_CERT_MICROSOFT_TOKEN`, `AR_CERT_ATLASSIAN_TOKEN`, `AR_CERT_GITHUB_TOKEN`
    - `AR_CERT_GDRIVE_TOKEN`, `AR_CERT_GCAL_TOKEN`, `AR_CERT_GMAIL_TOKEN`, `AR_CERT_OUTLOOK_TOKEN`, `AR_CERT_ONEDRIVE_TOKEN`, `AR_CERT_TEAMS_TOKEN`
    - `AR_CERT_JIRA_TOKEN` with `AR_CERT_JIRA_URL`, `AR_CERT_CONFLUENCE_TOKEN` with `AR_CERT_CONFLUENCE_URL`
    - `AR_CERT_REST_TOKEN` with `AR_CERT_REST_URL`
12. When `AR_CERT_OCR_GOOGLE`, `AR_CERT_OCR_AWS` or `AR_CERT_OCR_AZURE` is set, post one page to that named endpoint. Otherwise the OCR step is pending.
13. When `AR_GREENMAIL_SMTP` is set (`host:port`), send one notice through that SMTP server. Otherwise the mail step is pending. The integration job runs GreenMail and does not require this variable.

`fail` and `unverified` keep the scorecard off `live`. `skipped-no-token` does not.
