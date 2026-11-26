# Environments and configuration

## 1. Environments

| Environment | Purpose | Deployment | Data | Models |
|---|---|---|---|---|
| `dev` (local) | Developer laptops | Docker Compose (`make up`) + services via `uv run`/`pnpm dev` ([local-dev](local-dev.md)) | Seed data (`make seed`) | An OpenAI-compatible endpoint the developer names (`AR_DEV_MODEL_BASE_URL`) or connects on the Models screen |
| `ci` | Pull-request checks | Testcontainers + Temporal test server; `kind` cluster for e2e/Helm ([ci-cd](ci-cd.md)) | Ephemeral | The test library's model stand-in (`ar_testing.model_server`), registered by the tests as an ordinary provider |
| `staging` | Release candidates, eval gates, load tests | Helm, preset `small` (single-tenant) and `saas` (multi-tenant) | Synthetic tenants; anonymised copies never used | Company staging model endpoints |
| `prod` | Customers | Helm, preset `large` or `saas` ([helm-k8s](compose.md)) | Real | Company model endpoints |

Promotion: the same image digests move `ci → staging → prod`; only values differ ([ci-cd §6](ci-cd.md#6-releases-and-upgrades)).

## 2. Configuration rules

- All backend configuration is environment variables with prefix `AR_`, loaded by one `pydantic-settings` class per deployable that composes shared fragments from `ar_common.settings` (`DatabaseSettings`, `ValkeySettings`, `TemporalSettings`, `TelemetrySettings`, `S3Settings`, `SecretsSettings`, `InternalAuthSettings`). Unknown `AR_` variables log a warning at startup; missing required variables fail startup with a list of all missing names.
- Secrets (keys, passwords, tokens) come from Kubernetes Secrets (Helm `existingSecret` references) or files (`AR_*_FILE` variant accepted for every secret variable: the value is read from that path).
- Tenant-level behaviour is **not** configured by env vars; it lives in `tenants.settings` ([spec 02](../03-specs/02-identity-tenancy.md)). Env vars are platform/operator knobs.
- The web app reads only `AR_PUBLIC_URL`, `AR_API_INTERNAL_URL`, `AR_SESSION_GATE_TTL_S` and `NEXT_PUBLIC_*` build-time values ([spec 19](../03-specs/19-web-app.md)).
- `.env.example` at the repo root lists every variable. CI checks it against this catalogue (`scripts/check_env_catalogue.py`). Compose is the install ([compose](compose.md)).

## 3. Variable catalogue

Default = value when unset (dev-oriented); `(required)` = startup fails without it in `staging`/`prod`. "Defined in" links to the spec that owns the behaviour.

| Variable | Default | Description | Defined in |
|---|---|---|---|
| `AR_ACTIVITY_HEARTBEAT_THROTTLE_S` | `2` | How often, at most, a worker reports a running activity to Temporal. A stop reaches an activity with that report, so this is how long a reply keeps being written after a person presses Stop. Temporal's own default would be 24 seconds here | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_API_INTERNAL_URL` | `http://api:8000` | Internal base URL of `api` (used by web server-side and channels) | [spec 16](../03-specs/16-channels.md), [spec 19](../03-specs/19-web-app.md) |
| `AR_APPROVAL_NOTIFY_EMAIL` | empty | Extra mailbox that receives approval mail, in addition to the approvers named by the policy. Empty sends only to those approvers | [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_APPROVAL_WAIT_S` | `86400` | How long a run waits for an approval or a person's answer before the workflow expires the wait | [spec 07](../03-specs/07-agent-runtime.md), [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_ASGI_SERVER` | `uvicorn` | `uvicorn` or `granian` for api/channels/gateways | [stack](../stack.md) |
| `AR_AUDIT_ARCHIVE_BUCKET` | `ar-audit-archive` | Object Lock bucket for audit archives | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_AUTH_MODE` | empty (`password` in dev and ci, `oidc` otherwise) | `password` or `oidc`. Password is not the Helm default | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_BILLING_CURRENCY` | `INR` | Currency of platform model prices and the default `tenants.billing_currency` | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_BOOTSTRAP_ADMIN_EMAIL` | (required in single_tenant) | First tenant_admin; receives the invitation | [deployment-modes](../00-overview/deployment-modes.md) |
| `AR_BOOTSTRAP_TENANT_NAME` | `Default` | Single-tenant mode: display name of the bootstrap tenant | [deployment-modes](../00-overview/deployment-modes.md) |
| `AR_BOOTSTRAP_TENANT_SLUG` | (empty) | The tenant this install serves. The bootstrap Job creates a tenant with this slug (`default` when empty). Every process attaches to the tenant with this slug, read from the `tenants` table; when empty it attaches to the only tenant there is, and waits when there is none or more than one | [deployment-modes](../00-overview/deployment-modes.md), [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_CA_BUNDLE` | empty | Path of a PEM file added to outbound TLS trust, for a private certificate authority. `SSL_CERT_FILE` is used when this is empty. A customer database in `verify-ca` or `verify-full` uses this file when the URL does not set `sslrootcert`. | [egress](egress-closed.md) |
| `AR_CHANNELS_EMAIL_POLL_S` | `60` | IMAP poll interval for email channels | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNELS_PORT` | `8004` | Listen port of `channels` | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNELS_SLACK_UPDATE_INTERVAL_MS` | `1500` | Minimum interval between streamed Slack message edits | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNELS_TEAMS_UPDATE_INTERVAL_MS` | `2000` | Minimum interval between streamed Teams message updates | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNEL_LINK_TTL_S` | `900` | Lifetime of account-link tokens | [spec 16](../03-specs/16-channels.md) |
| `AR_CLAMAV_ADDRESS` | `clamav:3310` | clamd host:port for malware scanning | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_CLAMAV_TIMEOUT_S` | `10` | How long one clamd scan waits. A timeout rejects the upload. | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_CONSECUTIVE_TOOL_ERROR_LIMIT` | `8` | Run fails after this many consecutive tool errors | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_CSRF_ALLOWED_ORIGINS` | empty | Comma-separated origins that may send the session cookie, besides `AR_PUBLIC_URL`. Loopback names match each other only when `AR_ENV` is `dev` or `ci` | [spec 01](../03-specs/01-api-bff.md) |
| `AR_CURSOR_SECRET` | (secret) | HMAC for pagination cursors. Outside `dev` and `ci`, startup fails when this is missing or equal to `dev-cursor-secret` | [spec 01](../03-specs/01-api-bff.md) |
| `AR_DATABASE_URL` | (required) | Read registry | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_DATA_RESIDENCY` | empty | When set to `cluster`, model and embedding URLs must resolve to a private or loopback address. The stored tenant value `in` does not do this. Empty leaves the tenant column in charge. | [egress](egress-closed.md) |
| `AR_DB_APP_PASSWORD` | (required) | Password for `ar_app`, also the user in `AR_DATABASE_URL`. | [rls](../04-data/rls.md) |
| `AR_DB_CERT_DIR` | empty | Directory for customer-database TLS files. `sslcert` and `sslkey` must realpath under `<dir>/<tenant id>/`. A shared `sslrootcert` may realpath anywhere under `<dir>` that is not another tenant's folder. Empty refuses client certificates. `sslrootcert=system` and the `AR_CA_BUNDLE` file stay allowed. `/`, `/tmp`, `/etc` and `/proc` are refused as the directory. | [egress](egress-closed.md) |
| `AR_DB_CONNECT_DEADLINE_S` | `15` | Overall budget for dialling a customer database. Each address still uses `connect_timeout`, and at most `AR_DB_MAX_ADDRESSES` addresses are tried. | [egress](egress-closed.md) |
| `AR_DB_ENCRYPTION_ACTIVE_KEY` | `k1` | Active KEK id | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_DB_ENCRYPTION_KEYS` | (secret) | KEKs for `db_encrypted` | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_DB_MAX_ADDRESSES` | `4` | How many resolved addresses a customer-database dial will try. Every address is still screened before the first connect. | [egress](egress-closed.md) |
| `AR_DB_MIN_SSLMODE` | empty | Lowest libpq `sslmode` for a customer database. Empty imposes no floor except closed egress. | [egress](egress-closed.md) |
| `AR_DB_OWNER_PASSWORD` | (required) | Password for `ar_owner`. Unset, a placeholder, or the role name is refused. | [rls](../04-data/rls.md) |
| `AR_DB_PLATFORM_PASSWORD` | (required) | Password for `ar_platform`. | [rls](../04-data/rls.md) |
| `AR_DB_READONLY_PASSWORD` | (required) | Password for `ar_readonly`. | [rls](../04-data/rls.md) |
| `AR_DB_STRICT_TLS` | `true` | When true and `AR_EGRESS_CLOSED` is true, the floor is `AR_DB_STRICT_TLS_FLOOR`, so `require` is rejected. Set `false` to allow `require` (encrypted, unverified) on a closed install. | [egress](egress-closed.md) |
| `AR_DB_STRICT_TLS_FLOOR` | `verify-full` | `verify-full` or `verify-ca`. The default checks the server name. `verify-ca` applies only when the host is an IP literal. A hostname stays on `verify-full`. An invalid value stops the process. | [egress](egress-closed.md) |
| `AR_DEFAULT_CONTEXT_WINDOW` | `8000` | Compaction window when no model window is registered. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DELTA_COALESCE_MS` | `50` | Token delta coalescing window for stream events | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_DEPLOYMENT_MODE` | `single_tenant` | `saas` or `single_tenant` | [spec 01](../03-specs/01-api-bff.md) |
| `AR_DEV_MODEL_API_KEY` | (empty) | Dev only: API key for `AR_DEV_MODEL_BASE_URL` | [local-dev](local-dev.md) |
| `AR_DEV_MODEL_BASE_URL` | (empty) | Dev only: `make seed` registers this OpenAI-compatible endpoint. With none, no model is registered | [local-dev](local-dev.md) |
| `AR_DOCUMENT_ALIGN_COSINE` | `0.75` | Minimum cosine before two headings are paired when both have vectors. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_ALIGN_LEXICAL` | `0.5` | Minimum word overlap before two headings are paired. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_ASK_MAX_TOKENS` | `1800` | Output tokens one document model call may ask for. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_EXTRACT_TIMEOUT_S` | `900` | How long `documents.extract` may run. The gateway and the runtime client use this when it is longer than the stored tool timeout. | [document tasks](../09-plan/document-tasks.md) |
| `AR_TOOL_GATEWAY_GRACE_S` | `60` | Extra seconds the runtime waits on the tool gateway after the tool's own timeout. | [tools](../03-specs/08-tool-registry-mcp.md) |
| `AR_DOCUMENT_CHUNK_CHARS` | `1000` | Characters in one library passage. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CHUNK_OVERLAP` | `120` | Overlap between library passages. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_COLLECTION_CAP` | `20` | Collections searched in one page. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_BULLETS` | `40` | Bullets in one created section. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_COLUMNS` | `32` | Columns in one created sheet. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_FILE_BYTES` | `5242880` | Bytes in one created file. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_PAGES` | `30` | Pages in one created PDF. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_PARAGRAPHS` | `40` | Paragraphs in one created section. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_ROWS` | `500` | Rows in one created sheet. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_SECTIONS` | `40` | Sections in one created file. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_SHEETS` | `12` | Sheets in one created workbook. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_SLIDES` | `60` | Slides in one created deck. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_TEXT` | `4000` | Characters in one created paragraph. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CREATE_MAX_TITLE` | `200` | Characters in a created title. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_CROSSCHECK_MAX_CHARS` | `40000` | Characters of one document read in a single cross-check pass. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_DIFF_QUOTE_CHARS` | `600` | The most characters of each section `documents.diff` quotes, before and after. | [spec 24](../03-specs/24-documents.md) |
| `AR_DOCUMENT_EXCERPT_CHARS` | `1500` | Characters shown when a file does not fit the window. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_HEADING_CAP` | `15` | Outline entries and passage pages returned in one page. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_HISTORY_RESERVE` | `500` | Tokens held back for this turn's history. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_INSTRUCTION_RESERVE` | `2000` | Tokens held back for instructions. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_LISTED_ITEM_CAP` | `40` | Rows read from a delimited list into items. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_LOW_TEXT_CHARS` | `40` | Mean characters per page below this, after OCR, sets the `low_text` warning. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_MARGIN_RATIO` | `0.15` | Fraction of the context window held back as margin. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_MAX_BYTES` | `26214400` | Largest file the library will store. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_MAX_PAGES` | `600` | Largest page count one file may have. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_OUTPUT_RESERVE` | `4096` | Tokens held back from the context window for the answer. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_READ_CHARS` | `12000` | Characters one documents.read call returns. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_RETRIEVAL_BUDGET` | `12000` | Characters kept when no context window is registered. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_SEARCH_DOCUMENT_CAP` | `50` | Document ids one index search accepts. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_SEARCH_HITS` | `30` | Documents returned by one list page. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_SEARCH_SNIPPET_CHARS` | `240` | Characters in one search snippet. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_SEARCH_TOP_K` | `8` | Passages one search returns. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_SECTION_CAP` | `200` | Section readings one run will perform. The rest is reported unread. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_SOURCE_REF_CHARS` | `500` | Characters kept from a library source reference. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_TABLE_MAX_ROWS` | `2000` | Rows stored from one sheet. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_TABLE_PREVIEW_ROWS` | `8` | Rows shown in a sheet's passage preview. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_TASK_PARALLELISM` | `2` | Section readings in flight for one document task. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_TOKEN_FACTOR` | `1.15` | Multiplier on the ingest token counter when estimating a document. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_TOOL_RESERVE` | `1500` | Tokens held back for tool schemas. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_VISION_MAX_BYTES` | `8388608` | Bytes in one image a vision question may read. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DOCUMENT_ZIP_MEMBERS` | `30` | Members read from one zip. | [document tasks](../09-plan/document-tasks.md) |
| `AR_DURABLE_STATE` | (empty) | `postgres` binds HTTP state even under pytest; `memory` keeps the process cache. Empty uses Postgres outside pytest | M10 |
| `AR_EGRESS_ALLOW_LOOPBACK` | `false` | Whether a tool, a connector, a sandbox or a model provider may reach this machine's own addresses (`127.0.0.0/8`, `localhost`). Every process and every check reads this one setting; it does not follow from `AR_ENV`. The local stack (`.env.example`, `compose.yaml`) and the test run set it to `true`, because their model and tool servers are local | [tenancy and isolation](../02-architecture/tenancy-isolation.md) |
| `AR_EGRESS_ALLOW_NAMED_PRIVATE` | `false` | When `true`, a host named exactly on the allowlist may resolve to a private address. Metadata, unspecified, and decimal or mapped forms of those addresses stay denied. The air-gap overlay sets it to `true`. | [egress](egress-closed.md) |
| `AR_EGRESS_ALLOW_WILDCARD` | `false` | Whether `*` (reach any host) is honoured in a sandbox egress allowlist. Off in production, so an allowlist names its hosts. A setting of the install, not a consequence of `AR_ENV`. | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_EGRESS_CLOSED` | `false` | When `true`, model calls, embeddings, connectors, knowledge fetches, web search, outbound mail, SIEM URLs, web push and the OTEL exporter may only dial a host on the tenant allowlist or `AR_EGRESS_HOSTS`. An empty list means no outbound. Default `false`, so an existing cloud model provider keeps working. The air-gap Helm overlay sets it to `true`. | [egress](egress-closed.md) |
| `AR_EGRESS_DENY_CIDRS` | metadata + RFC1918 + cluster | CIDRs always denied for sandbox/tool egress | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_EGRESS_HOSTS` | empty | Comma-separated hosts the install may reach while `AR_EGRESS_CLOSED` is on, even when a tenant list is empty. The air-gap overlay starts from `otel-collector` and appends this value and `airgap.egressHosts`. | [egress](egress-closed.md) |
| `AR_EGRESS_KEEPALIVE_S` | `60` | Seconds an idle connection to a model, embedding or rerank provider stays open for the next call from the same process. Reuse saves a TCP and a TLS handshake on each call, measured at about 0.6 s to a cloud provider. Every request on a kept connection still passes the egress decision. `0` closes each connection when its call ends | [egress](egress-closed.md#connection-reuse) |
| `AR_EGRESS_PROXY_URL` | `http://squid:3128` | For the page tools and remote MCP outside the cluster | [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 10](../03-specs/10-knowledge.md) |
| `AR_EMBEDDING_RETRIES` | `2` | How often an embedding or rerank request is sent again after the provider answered 429 or 503. The wait is the provider's `Retry-After`, or 1, 2 and 4 seconds, and never more than 10. `0` turns it off; the most is `5` | [spec 10](../03-specs/10-knowledge.md) |
| `AR_EMBEDDING_TIMEOUT_S` | unset | HTTP timeout for one embedding or rerank request. Unset takes the provider's own timeout, and `60` when that is not set | [spec 10](../03-specs/10-knowledge.md) |
| `AR_ENV` | `dev` | `dev`, `ci`, `staging`, `prod`; dev-only features (Docker sandbox driver, API docs UI) are refused when `prod`. The product holds no scripted turn, demo tool server or model stand-in in any environment (M38a) | [local-dev](local-dev.md) |
| `AR_EVAL_CONCURRENCY` | `4` | Parallel cases per eval run | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_FASTEMBED_CACHE_DIR` | `/var/cache/fastembed` | BM25 model cache for the optional qdrant adapter (pre-baked in image for air-gapped) | [spec 10](../03-specs/10-knowledge.md) |
| `AR_FETCH_PER_HOST_PER_MINUTE` | `30` | The most requests a minute the page tools (`general.fetch`, `web.discover`, `documents.ingest` by URL) send to one host, for the whole install. A site's `Crawl-delay` lowers it for that site | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_FILES_PROXY_DOWNLOADS` | `false` | Stream downloads through `api` instead of presigned URLs | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_FILES_SCANNER` | `clamav` | `clamav` or `none`; the scanner run over every upload. A setting of the install, not a consequence of `AR_ENV`. When it is `clamav` and `AR_CLAMAV_ADDRESS` does not answer, the upload is rejected. | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_FILE_EXPIRY_MAX_SECONDS` | `2592000` | Longest `expiresAfterSeconds` on an upload. | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_FILE_EXPIRY_MIN_SECONDS` | `3600` | Shortest `expiresAfterSeconds` on an upload. | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_GUARDRAIL_INPUT_ALIAS` | `fast` | Model alias for the input safety classifier (empty disables) | [prompt-injection §4](../06-security/prompt-injection.md) |
| `AR_GUARDRAIL_OUTPUT_ALIAS` | `fast` | Model alias for the output safety classifier (empty disables) | [prompt-injection §4](../06-security/prompt-injection.md) |
| `AR_HTTP_USER_AGENT` | `agentic-runtime` | The User-Agent every outbound request carries, and the name a site's robots.txt is matched on (the part before any `/`). An install that reads public pages adds a contact address, for example `acme-agents/1.0 (+https://acme.example/contact)` | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_INGEST_ACTIVITY_CONCURRENCY` | `32` | Per worker | [spec 10](../03-specs/10-knowledge.md) |
| `AR_INGEST_INLINE_MAX_BYTES` | `262144` | The largest file sent to a connected ingest worker with the request. A larger upload is read by the worker from the file store. With a worker connected the API parses only a larger file that is in no file store | [document tasks](../09-plan/document-tasks.md) |
| `AR_INGEST_MAX_BYTES` | `209715200` | Maximum size of a single ingested document | [spec 10](../03-specs/10-knowledge.md) |
| `AR_INGEST_SYNC_CONCURRENCY` | `16` | Child workflows per sync | [spec 10](../03-specs/10-knowledge.md) |
| `AR_INJECTION_CLASSIFIER_TIMEOUT_MS` | `1000` | Timeout for the tool-result injection classifier (fail-open with flag) | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_INPUT_WAIT_TIMEOUT_S` | `1800` | Elicitation wait | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_INSTALL_ID` | derived from the database address (`host:port/name`) | Names this install on a container host it may share. Sandbox containers carry it as a label, and the orphan sweep touches only containers with this id. Set it only when two installs could derive the same value | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_INTERNAL_AUTH_SECRET` | (unset) | Shared HMAC for `sandbox-manager`, `mcp-gateway`, and `/metrics`. Empty fails closed | [internal-apis](../05-contracts/internal-apis.md) |
| `AR_INTERNAL_JWT_JWKS` | `http://api:8000/internal/v1/.well-known/jwks.json` | JWKS URL or inline JSON for verifying internal JWTs | [internal-apis](../05-contracts/internal-apis.md) |
| `AR_INTERNAL_JWT_PRIVATE_KEY` | (required) | Ed25519 PEM for signing internal service JWTs; mounted Secret | [authn-authz §8](../06-security/authn-authz.md) |
| `AR_INVITATION_TTL_DAYS` | `7` | How long a mailed invitation can be accepted | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_KNOWLEDGE_FETCH_MAX_BYTES` | `2000000` | Characters kept from one fetched page. | [spec 10](../03-specs/10-knowledge.md) |
| `AR_KNOWLEDGE_MIN_SCORE` | (unset) | Install default for chat retrieval. A chunk must clear this rerank or similarity score. The agent and the tenant can override it | [spec 10](../03-specs/10-knowledge.md) |
| `AR_KNOWLEDGE_RERANK_CANDIDATES` | `50` | Candidates passed to the reranker | [spec 10](../03-specs/10-knowledge.md) |
| `AR_KNOWLEDGE_SEARCH_MAX_HITS` | `20` | Hits one knowledge search returns. | [spec 10](../03-specs/10-knowledge.md) |
| `AR_LLM_MAX_TOKENS` | `1024` | Default `max_tokens` for an OpenAI-compatible chat call when the model row sets no output limit. A case or a caller may ask for less. The model limit is the ceiling | [spec 04](../03-specs/04-model-gateway.md), [live-certification](../09-plan/live-certification.md) |
| `AR_LOGIN_LOCKOUT_S` | `300` | How long a locked sign-in stays locked. State is in Valkey | [spec 01](../03-specs/01-api-bff.md) |
| `AR_LOGIN_MAX_ATTEMPTS` | `10` | Failed sign-ins before the shared lockout | [spec 01](../03-specs/01-api-bff.md) |
| `AR_LOG_HASH_USER_IDS` | `false` (`true` in saas) | Hash user ids in logs and Langfuse | [data-protection](../06-security/data-protection.md) |
| `AR_MAX_DEPTH` | `3` | Platform cap for subagents | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_MAX_JSON_BODY_BYTES` | `1048576` | Maximum JSON request body | [spec 01](../03-specs/01-api-bff.md) |
| `AR_MAX_MESSAGE_CHARS` | `100000` | Maximum user message length | [spec 06](../03-specs/06-conversations-runs.md) |
| `AR_MCPG_PORT` | `8002` | Listen port of `mcp-gateway` | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_MCP_GATEWAY_URL` | `http://localhost:8002` | Internal URL of `mcp-gateway` | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS` | cluster CIDRs | CIDRs `internal_http` tool servers may resolve to | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_MEMORY_DEDUPE_SIM` | `0.92` | Cosine similarity above which facts are merged | [spec 11](../03-specs/11-memory.md) |
| `AR_MEMORY_RECALL_MIN_SIM` | `0.25` | Minimum similarity for memory recall | [spec 11](../03-specs/11-memory.md) |
| `AR_MG_CB_FAILURES` | `5` | Consecutive failures to open | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_CB_OPEN_S` | `30` | Circuit-breaker open duration | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_FALLBACK_BACKOFF_S` | `0.2` | Seconds times the attempt number before the next fallback model | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_HEALTH_INTERVAL_S` | `30` | Provider health probe interval | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_MAX_FALLBACKS` | `2` | Maximum fallback hops per request | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_PORT` | `8001` | Listen port of `model-gateway` | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_SEMAPHORE_WAIT_S` | `10` | Max wait for a concurrency slot before 429 | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MODEL_GATEWAY_URL` | `http://localhost:8001` | Internal URL of `model-gateway` | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_MODEL_PROVIDER_DENY_CIDRS` | RFC1918 + link-local + cluster CIDRs (SaaS) | SSRF guard for tenant providers | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_OIDC_AUDIENCE` | `ar-api` | Expected audience of integrator access tokens | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_OIDC_CLIENT_ID` | empty | OIDC client id. Required with the issuer | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_OIDC_CLIENT_SECRET` | (secret, empty) | OIDC client secret. Never logged or returned | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_OIDC_ISSUER` | empty | Customer OIDC issuer. Required outside dev and ci when auth mode is `oidc` | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_OIDC_JWKS_URL` | issuer JWKS | Override for the JWKS document | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_OIDC_MFA_ACR` | `mfa,otp` | `acr` values that count as MFA | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OIDC_MFA_AMR` | `mfa,otp,hwk,pop` | `amr` values that count as MFA | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OIDC_REDIRECT_URL` | `{AR_PUBLIC_URL}/api/v1/auth/callback` | Authorization-code redirect | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OIDC_REQUIRE_MFA` | `true` | Access and id tokens must carry a configured `amr` or `acr` | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_OPA_BUNDLE_TOKEN` | secret | Bearer token OPA uses to fetch the policy bundle from `api`. Empty is refused outside dev and ci. `scripts/dev_keys.py` generates it | [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_OPA_TIMEOUT_MS` | `200` | Policy decision timeout (fail closed) | [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_OPA_URL` | `http://opa:8181` | OPA decision API URL | [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_OTEL_EXPORTER_OTLP_ENDPOINT` | (empty) | OTLP gRPC endpoint. Empty, `off`, or `none` disables export. Set `http://otel:4317` when the `obs` profile is running. Export is batched and dropped when the collector is absent | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_OUTBOX_BATCH_SIZE` | `500` | Rows per outbox relay batch | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_PASSWORD_LOGIN` | `false` | Explicit opt-in for password sign-in on a single-tenant install outside dev and ci | [ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md) |
| `AR_PASSWORD_MFA` | `false` | When true, password sign-in also requires the user's TOTP | [spec 01](../03-specs/01-api-bff.md) |
| `AR_PASSWORD_MIN_LENGTH` | `8` | The shortest password a reset accepts. Not below 8 | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_PASSWORD_RESET_TTL_MINUTES` | `120` | How long a mailed password-reset link works | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_PGVECTOR_DIMENSIONS` | `1024` (memory and tool-search embeddings only; knowledge supports 384/768/1024/1536/3072, [spec 10 §7.1](../03-specs/10-knowledge.md#71-storage); fixed; changing requires a migration and re-embed job `scripts/reembed_memory.py`) |  | [spec 11](../03-specs/11-memory.md) |
| `AR_PII_LANGUAGE_MODEL` | `en_core_web_sm` | The installed spaCy model the personal-data recognisers use. The default ships with the product. A deployment that masks names and places installs a larger model and names it here; a name that is not installed stops the first masking with an error, and nothing is downloaded | [data protection §5](../06-security/data-protection.md#5-pii-handling) |
| `AR_PLATFORM_DB_DENY_CIDRS` | empty | Comma-separated CIDRs of the platform database pods and services. A resolved address inside one of them is refused. The chart copies `cluster.podCIDR` and `cluster.serviceCIDR`. | [egress](egress-closed.md) |
| `AR_PLATFORM_DB_DENY_HOSTS` | empty | Comma-separated platform database service names. A customer DSN whose host is one of these, or whose resolved address matches one of them, is refused on any port. The chart fills the bundled CNPG `-rw`, `-ro`, `-r` and `-pooler` names. | [egress](egress-closed.md) |
| `AR_PUBLIC_URL` | `http://localhost:3000` | Origin of the web app (cookies, CSRF origin check, redirects, review links and approval cards) | [spec 01](../03-specs/01-api-bff.md), [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 16](../03-specs/16-channels.md), [spec 19](../03-specs/19-web-app.md) |
| `AR_REVIEW_LINK_TTL_S` | `86400` | How long a signed one-item review link stays valid. The link also ends when the approval expires | [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_QDRANT_API_KEY` | (secret, unset) | Qdrant API key; only with the optional qdrant adapter | [spec 10](../03-specs/10-knowledge.md) |
| `AR_QDRANT_URL` | (unset) | Qdrant URL; required only when `AR_VECTOR_BACKEND=qdrant` or a collection uses the qdrant adapter (local `qdrant` profile: `http://localhost:6333`) | [spec 10](../03-specs/10-knowledge.md) |
| `AR_RETENTION_SWEEP_CRON` | `0 1 * * *` | Schedule of `RetentionSweepWorkflow` | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_ROUTINE_MIN_INTERVAL_S` | `300` | Minimum schedule interval for routines | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_ROUTINE_DEFAULT_MAX_STEPS` | `16` | Step ceiling for a routine that names no budget | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_ROUTINE_DEFAULT_MAX_TOOL_CALLS` | `16` | Tool-call ceiling for a routine that names no budget | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_ROUTINE_DEFAULT_MAX_TOKENS` | `80000` | Token ceiling for a routine that names no budget | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_ROUTINE_DEFAULT_MAX_COST_MICROS` | `4000000` | Cost ceiling for a routine that names no budget | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_ROUTINE_DEFAULT_MAX_WALL_CLOCK_S` | `600` | Wall-clock ceiling for a routine that names no budget | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_EXTRACTION_MIN_CONFIDENCE` | `0.8` | A verified quote below this is low-confidence | [spec 24](../03-specs/24-documents.md) |
| `AR_REGISTERED_SCRIPT_ENTRY` | `python model.py --params params.json` | Fixed command for a registered script. The model does not choose it | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_RUNTIME_MAX_CONCURRENT_ACTIVITIES` | `200` | Per worker process | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_RUNTIME_MAX_CONCURRENT_WORKFLOW_TASKS` | `100` | Temporal worker workflow-task slots | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_RUNTIME_TENANT_MAX_ACTIVE_RUNS` | `50` (plan `max_concurrent_runs` takes precedence when lower) | Per-tenant cap of concurrently executing runs (excess runs stay `queued`) | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| `AR_RUN_HISTORY_STEPS` | `24` | Activities one `AgentRunWorkflow` execution records before continue-as-new. The run budget's `max_steps` is still the cap on work | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_RUN_STREAM_TTL_S` | `86400` | TTL of Valkey run event streams | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_S3_ACCESS_KEY_ID` | (empty → IRSA/instance role) | Object store credentials | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_BUCKET` | `ar-files` | Bucket for files and artifacts | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_ENDPOINT` | `http://localhost:8333` | Internal endpoint | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_PRESIGN_TTL_S` | `300` | Presigned URL lifetime | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_PUBLIC_ENDPOINT` | `http://localhost:8333` | Browser-reachable endpoint for presigned URLs | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_REGION` | `us-east-1` | Object store region | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_SECRET_ACCESS_KEY` | (empty → IRSA/instance role) | Object store credentials | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_SSE` | `AES256` | `none` to disable | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_SAAS_SELF_SIGNUP` | `false` | Unused. Self-serve signup was removed in Stage 7 and this flag does not mount a route | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_SANDBOX_ALLOWED_REGISTRIES` | `registry.local/ar` | Registries sandbox template images may come from | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_ALLOW_UNISOLATED` | `false` | Whether a sandbox may run without kernel isolation (the `docker` driver). Nothing runs on the host itself, whatever this is set to. Off in production. A setting of the install, not a consequence of `AR_ENV`. | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_DOCKER_NETWORK` | empty | Internal Docker network for sandbox containers. Compose sets `agentic-runtime_sandbox`. | [compose](compose.md) |
| `AR_SANDBOX_DOCKER_NETWORK` | empty | Internal docker network the in-process launcher attaches a sandbox container to; empty publishes the agent port to loopback (dev) | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_DOCKER_RUNTIME` | `runc` | `runsc` if installed | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_DRIVER` | `kubernetes`; `docker` when `AR_SANDBOX_ALLOW_UNISOLATED` is on and none is named | `kubernetes`, or `docker` for one machine. The docker driver shares the host kernel and does not confine the network, so it needs `AR_SANDBOX_ALLOW_UNISOLATED` | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_EGRESS_PROXY` | empty | Squid URL for a confined sandbox. Compose sets `http://squid:3128`. | [compose](compose.md) |
| `AR_SANDBOX_ENSURE_TIMEOUT_S` | `30` | How long a call waits for a computer's scope while another call or the sweep holds it; after that it is refused as busy | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_IMAGE` | empty; the chart sets `sandboxes.image`, or `ar-sandbox` at `global.imageTag` | The one image every computer starts from, for the `kubernetes` and the `docker` driver. The sandbox manager reads it; a dev API or worker reads it when it starts containers itself. With no image, starting a computer fails and names this setting | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_LOCK_TTL_S` | `300` | How long one process may hold a computer's scope while it starts, suspends or resumes it, before the lock expires on its own | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_MANAGER_URL` | empty | Internal URL of `sandbox-manager`. `compose.computers.yaml` sets it to `http://sandbox-manager:8003`. Empty in staging or production means the install has no computers: a tool that needs one is refused in words | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_SANDBOX_MAX_PER_TENANT` | plan `max_concurrent_sandboxes` (default 50) | Hard cap of concurrent sandboxes per tenant | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_ORPHAN_GRACE_S` | `120` | A sandbox container or host folder younger than this is never removed as an orphan, because its row may not be saved yet | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_PACKAGE_MIRRORS` | empty | JSON `{pypi,npm,apt}` mirror URLs | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_REAP_INTERVAL_S` | `60` | How often the sweep runs that suspends idle computers, ends expired ones and removes orphaned containers: the interval of the `sandbox-reaper` schedule, and of the timer in a process that starts containers itself | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_SNAPSHOT_INTERVAL_S` | `600` | Periodic workspace snapshot interval while active | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_SNAPSHOT_MAX_MB` | `256` | The largest compressed working folder a suspend keeps. A computer with a larger one is not suspended and keeps running until its lifetime ends | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_WARM_POOL` | `default=4,browser=2` | Warm pods per template | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SEARCH_API_KEY` | (empty) | Key for the configured web search provider. Never logged, returned, or committed. CI leaves it empty and the live search test skips (`not_live`) | [M21b](../09-plan/M21b-general-tools.md) |
| `AR_SEARCH_BASE_URL` | empty | Install-wide SearXNG address. A tenant `search.baseUrl` wins. Used when the tenant has not set a provider and `AR_SEARCH_PROVIDER` is unset. | [egress](egress-closed.md) |
| `AR_SEARCH_PROVIDER` | `none` | `none`, `brave` or `tavily`. Empty results until a provider answers. A tenant `search.secretName` wins over this key | [M21b](../09-plan/M21b-general-tools.md) |
| `AR_SECRETS_BACKEND` | `db_encrypted` (local) / `vault` (prod) | Backend selection | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_SECRET_CACHE_TTL_S` | `60` | In-process cache | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_SESSION_ENCRYPTION_KEY` | (secret, 32 bytes b64) | Encrypt tokens stored in sessions | [spec 01](../03-specs/01-api-bff.md) |
| `AR_SESSION_ENCRYPTION_KEY_PREVIOUS` | (empty) | Previous session key accepted for decryption during rotation | [secrets](../06-security/secrets.md) |
| `AR_SESSION_GATE_TTL_S` | `15` | How long the web session gate reuses one confirmed session. A prefetch does not start a session call | [spec 19](../03-specs/19-web-app.md) |
| `AR_SESSION_MAX_AGE_S` | `604800` | Absolute session max | [spec 01](../03-specs/01-api-bff.md) |
| `AR_SESSION_TTL_S` | `43200` | Sliding session TTL | [spec 01](../03-specs/01-api-bff.md) |
| `AR_SMTP_FROM` | `Cura Works <no-reply@localhost>` | Sender address | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_HOST` | (empty) | The mail server the product sends through: invitations, and a routine's email delivery that names no email integration ([spec 15 §4](../03-specs/15-routines-triggers.md#4-delivery-phase-in-complete_routine_event-after-the-run-has-ended)). Read by `api` and `system-worker`. While it is empty no mail is sent and a delivery fails saying so. Mailpit in dev | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_PASSWORD` | (empty) | SMTP auth password (Secret) | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_PORT` | `1025` | SMTP port | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_STARTTLS` | `false` (dev) | Use STARTTLS | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_USERNAME` | (empty) | SMTP auth user | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SSE_MAX_PER_USER` | `20` | Concurrent SSE streams per user | [spec 01](../03-specs/01-api-bff.md) |
| `AR_TRUSTED_PROXY_CIDRS` | `127.0.0.0/8,::1/128` | The proxies in front of the API (the web app, an ingress), as CIDRs. A request from one of them is counted against the visitor named in `X-Forwarded-For`; any other request is counted against its own address | [spec 16 §7](../03-specs/16-channels.md) |
| `AR_STEP_UP_TTL_S` | `600` | Step-up validity | [spec 01](../03-specs/01-api-bff.md), [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_TABLE_MAX_ROWS` | `1000000` | The most rows of one table file (CSV, TSV, JSON or a sheet of an xlsx) the table tools read. A longer file is refused, never read in part. Rows are held in the in-process query engine while one statement runs | [OQ-152](../open-questions.md) |
| `AR_TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend host:port. `/readyz` always checks it. A turn is not run in the API process when the worker cannot take it (`interrupted` / `not_resumed`) | [spec 01](../03-specs/01-api-bff.md), [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_TEMPORAL_NAMESPACE` | `agentic-runtime` | One namespace per environment; dedicated tenants may get their own (`AR_TENANT_TEMPORAL_NAMESPACES`) | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_TENANT_DB_ROUTES` | `{}` | JSON map `tenant_id → database URL` for `dedicated_db` tenants | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| `AR_TENANT_DELETE_GRACE_DAYS` | `7` | Grace period before tenant data deletion | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_TENANT_TEMPORAL_NAMESPACES` | `{}` | JSON map `tenant_id → Temporal namespace` for dedicated tenants | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| `AR_TOKEN_CACHE_KEY` | (secret) | Encrypts cached access tokens in Valkey | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_TOOL_DRIFT_INTERVAL` | `1h` | Tool manifest drift check interval | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_TOOL_RESULT_MAX_FILE_BYTES` | `20971520` | 20 MiB | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_TOOL_WORKER_THREADS` | `16` | How many threads a process has for the waiting that tool calls do: a network request, a command, a sleep. A tool's own code stays on the event loop's thread; only the wait runs on one of these, so the process goes on serving while a tool waits. More waits than threads queue | [spec 07 §10](../03-specs/07-agent-runtime.md#10-configuration) |
| `AR_TRACE_SAMPLE_RATIO` | `0.1` | Head sampling ratio (errors kept by tail sampling) | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_TRACE_UI_URL` | `http://localhost:3001` | Base URL used to build `trace_url` links to the trace UI | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_USAGE_ROLLUP_INTERVAL` | `15m` | `usage_daily` rollup interval | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_VALKEY_URL` | (required) | Caches, semaphores, circuit state, quota counters | [spec 04](../03-specs/04-model-gateway.md), [spec 16](../03-specs/16-channels.md) |
| `AR_VAULT_ADDR` | `http://localhost:8200` | OpenBao/Vault address | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_AUTH` | `kubernetes` | `kubernetes` or `token` | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_KV_MOUNT` | `ar` | KV v2 mount | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_ROLE` | `ar-{service}` | Kubernetes auth role | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_TOKEN` | (dev) | Token auth | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VECTOR_BACKEND` | `pgvector` | Retrieval backend for new knowledge collections and migration target: `pgvector` \| `qdrant` | [spec 10](../03-specs/10-knowledge.md#11-configuration), [ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md) |
| `AR_VECTOR_MIGRATION_RETAIN_HOURS` | `24` | Rollback window after a retrieval backend switch | [spec 10](../03-specs/10-knowledge.md#9-migrating-between-backends) |
| `AR_VECTOR_PG_EF_SEARCH` | `100` | `hnsw.ef_search` for knowledge searches on pgvector | [spec 10](../03-specs/10-knowledge.md#73-hybrid-query-one-sql-statement-per-search) |
| `AR_VECTOR_PG_READ_DSN` | (unset) | Optional read-replica DSN for knowledge searches on pgvector | [spec 10](../03-specs/10-knowledge.md#11-configuration), [scaling](scaling.md) |
| `AR_WEBHOOK_ALLOW_PRIVATE` | `false` | Allow webhook targets in private ranges (dev only) | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_WEBHOOK_SWEEP_GRACE_S` | `120` | Extra seconds after a delivery is due before the sweep retries it while Temporal is up | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_EXTRACTION_BOOLEAN_SYNONYMS` | `yes,true,y;no,false,n` | Words a quote may use for true, then false, separated by a semicolon | [spec 24](../03-specs/24-documents.md) |

### 3.1 Variables added for records, grounding and packs

These names are part of the catalogue. The task that implements each one adds it to `ar_common.settings` and `.env.example` in the same change. They are not required for M1.

| Variable | Default | Description | Defined in |
|---|---|---|---|
| `AR_BINDER_MAX_ITEMS` | `5000` | Maximum records in one binder selection | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_BUCKET` | `ar-evidence` | Object Lock bucket for evidence bytes | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_DEFAULT_LOCK_DAYS` | `2555` | Object Lock retain-until offset | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_LOCK_MODE` | `compliance` | `compliance` or `governance` | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_SIGNING_KEY` | (secret) | Ed25519 PEM for evidence and run-record manifests | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_SIGNING_KEY_ID` | `evidence-k1` | `signature_key_id` written on new items | [spec 21](../03-specs/21-records-governance.md) |
| `AR_GROUNDING_MAX_SENTENCES` | `200` | Claim cap per answer | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_GUEST_MAGIC_LINK_TTL_S` | `900` | Guest magic-link lifetime | [spec 21](../03-specs/21-records-governance.md) |
| `AR_GUEST_MAX_TTL_DAYS` | `90` | Longest guest principal lifetime | [spec 21](../03-specs/21-records-governance.md) |
| `AR_GUEST_SESSION_TTL_S` | `28800` | Guest session TTL | [spec 21](../03-specs/21-records-governance.md) |
| `AR_PACK_SIGNATURE_REQUIRED` | `true` (`false` when `AR_ENV=dev`) | Reject unsigned content packs | [spec 05](../03-specs/05-agent-registry.md) |
| `AR_PACK_TRUSTED_KEYS` | (secret JSON) | `{key_id, public_key_pem}` entries | [spec 05](../03-specs/05-agent-registry.md) |
| `AR_PACKS_DIR` | `packs` | Directory scanned for pack packages and task templates. The service image holds `packs/examples/task-templates` there and no other pack; mount a folder to add more | [spec 21](../03-specs/21-records-governance.md) |
| `AR_RUN_RECORD_MAX_BLOB_BYTES` | `52428800` | Max encrypted tool I/O stored with a run record | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_TSA_TIMEOUT_MS` | `2000` | RFC 3161 call timeout | [spec 21](../03-specs/21-records-governance.md) |
| `AR_TSA_URL` | empty | Platform TSA used when a tenant enables timestamping without its own URL | [spec 21](../03-specs/21-records-governance.md) |

### 3.2 Required versus defaulted

A deployment starts once secrets and identity exist. Every other variable in §3 and §3.1 has a default and must not be set for a normal tenant.

Required in `staging` and `prod` (startup fails when missing):

| Variable | Why it cannot be guessed |
|---|---|
| `AR_DATABASE_URL` | The database |
| `AR_VALKEY_URL` | The cache |
| `AR_INTERNAL_JWT_PRIVATE_KEY` | Service identity |
| `AR_SESSION_ENCRYPTION_KEY` | Session cookie contents |

Everything else, including evidence, guests, packs and grounding, runs on the default in the catalogue. Tenant behaviour lives in `tenants.settings` with the defaults in the owning spec. Settings screens use Simple and Advanced modes ([spec 19 §12](../03-specs/19-web-app.md#12-simple-and-advanced-settings)).

### 3.3 Local host ports

These are laptop publish ports. They are not set in Helm. `make ports-check` copies a non-default value into the localhost URL named in [local-dev](local-dev.md#5-host-ports). `AR_MG_PORT`, `AR_MCPG_PORT`, `AR_CHANNELS_PORT` and `AR_SMTP_PORT` are already in §3 and are the host ports for those processes.

| Variable | Default | Description | Defined in |
|---|---|---|---|
| `AR_CLICKHOUSE_HOST_PORT` | `8123` | Host port for ClickHouse HTTP | [local-dev](local-dev.md#5-host-ports) |
| `AR_CLAMAV_HOST_PORT` | `3310` | Host port for clamd. Updates `AR_CLAMAV_ADDRESS` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_EGRESS_HOST_PORT` | `3128` | Host port for Squid. Updates `AR_EGRESS_PROXY_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_GRAFANA_HOST_PORT` | `3001` | Host port for Grafana. Updates `AR_TRACE_UI_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_INGEST_HOST_PORT` | `8014` | Host port for ingest-worker health | [local-dev](local-dev.md#5-host-ports) |
| `AR_LANGFUSE_HOST_PORT` | `3100` | Host port for Langfuse | [local-dev](local-dev.md#5-host-ports) |
| `AR_MAILPIT_UI_HOST_PORT` | `8025` | Host port for the Mailpit UI | [local-dev](local-dev.md#5-host-ports) |
| `AR_OPA_HOST_PORT` | `8181` | Host port for OPA. Updates `AR_OPA_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_OTEL_GRPC_HOST_PORT` | `4317` | Host port for OTLP gRPC. Updates `AR_OTEL_EXPORTER_OTLP_ENDPOINT` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_OTEL_HTTP_HOST_PORT` | `4318` | Host port for OTLP HTTP | [local-dev](local-dev.md#5-host-ports) |
| `AR_PG_HOST_PORT` | `5432` | Host port for Postgres. Updates `AR_DATABASE_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_PORT` | `8000` | API listen port and host port. Updates `AR_API_INTERNAL_URL` and `API_PROXY_URL` | [local-dev](local-dev.md#5-host-ports) |
| `AR_API_PORT` | | When set, the API listens here instead of `AR_PORT`. The web dev proxy follows it unless `AR_API_URL` is set. | [live-certification](../09-plan/live-certification.md) |
| `AR_API_URL` | | Full API origin for live certification and the web proxy. Wins over `AR_API_PORT`. | [live-certification](../09-plan/live-certification.md) |
| `AR_EMBED_MODEL` | `Qwen/Qwen3-Embedding-8B` | Embedding model the live certification registers on the `embed` alias. DeepInfra also serves `BAAI/bge-m3`. | [live-certification](../09-plan/live-certification.md) |
| `AR_EVAL_MIN_PASS_RATE` | `1` | Live eval fails when `pass_rate` is below this, or when every case errored. | [live-certification](../09-plan/live-certification.md) |
| `AR_SECOND_EMAIL` | | Optional second seeded person. Requires `AR_SECOND_PASSWORD`. | [live-certification](../09-plan/live-certification.md) |
| `AR_SECOND_PASSWORD` | | Password for `AR_SECOND_EMAIL`. | [live-certification](../09-plan/live-certification.md) |
| `AR_SECOND_NAME` | | Display name for the second person. | [live-certification](../09-plan/live-certification.md) |
| `AR_SECOND_ROLE` | `approver` | Role key for the second person. | [live-certification](../09-plan/live-certification.md) |
| `AR_PROMETHEUS_HOST_PORT` | `9090` | Host port for Prometheus | [local-dev](local-dev.md#5-host-ports) |
| `AR_QDRANT_GRPC_HOST_PORT` | `6334` | Host port for Qdrant gRPC | [local-dev](local-dev.md#5-host-ports) |
| `AR_QDRANT_HTTP_HOST_PORT` | `6333` | Host port for Qdrant HTTP. Updates `AR_QDRANT_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_RUNTIME_HOST_PORT` | `8012` | Host port for runtime-worker health | [local-dev](local-dev.md#5-host-ports) |
| `AR_S3_HOST_PORT` | `8333` | Host port for SeaweedFS S3. Updates `AR_S3_ENDPOINT` and `AR_S3_PUBLIC_ENDPOINT` | [local-dev](local-dev.md#5-host-ports) |
| `AR_SANDBOX_AGENT_HOST_PORT` | `8080` | Host port for sandbox-agent | [local-dev](local-dev.md#5-host-ports) |
| `AR_SANDBOX_MANAGER_HOST_PORT` | `8003` | Host port for sandbox-manager | [local-dev](local-dev.md#5-host-ports) |
| `AR_SYSTEM_HOST_PORT` | `8013` | Host port for system-worker health | [local-dev](local-dev.md#5-host-ports) |
| `AR_TEMPO_HOST_PORT` | `3200` | Host port for Tempo | [local-dev](local-dev.md#5-host-ports) |
| `AR_TEMPORAL_HOST_PORT` | `7233` | Host port for Temporal gRPC. Updates `AR_TEMPORAL_ADDRESS` | [local-dev](local-dev.md#5-host-ports) |
| `AR_TEMPORAL_UI_HOST_PORT` | `8233` | Host port for the Temporal UI | [local-dev](local-dev.md#5-host-ports) |
| `AR_VALKEY_HOST_PORT` | `6379` | Host port for Valkey. Updates `AR_VALKEY_URL` | [local-dev](local-dev.md#5-host-ports) |
| `AR_VAULT_HOST_PORT` | `8200` | Host port for OpenBao. Updates `AR_VAULT_ADDR` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_WEB_HOST_PORT` | `3000` | Host port for the web app. Updates `AR_PUBLIC_URL` | [local-dev](local-dev.md#5-host-ports) |

## 4. Mirrors and air-gapped installs

| What | Variable / value | Notes |
|---|---|---|
| Container images | Helm `global.imageRegistry` | All images (ours and dependencies) pulled from the customer registry; `make images-bundle` produces a tarball + manifest |
| Sandbox images | `AR_SANDBOX_ALLOWED_REGISTRIES` | Only these registries are accepted for templates |
| Package mirrors in sandboxes | `AR_SANDBOX_PACKAGE_MIRRORS` | JSON `{pypi, npm, apt}` URLs written into the sandbox (`pip.conf`, `.npmrc`, apt sources) |
| BM25 model for the optional qdrant adapter | `AR_FASTEMBED_CACHE_DIR` | Pre-baked in the image or a pre-populated volume; no downloads at runtime when `AR_ENV=prod`; unused with the default pgvector adapter |
| Python/Node build deps | `UV_INDEX_URL`, `npm_config_registry` (build-time) | Used by Dockerfiles and CI only |
