# Spec 04: Model gateway (`model-gateway`) and model registry (`ar_domain.models`)

Deployable `model-gateway` (`services/model_gateway`, package `ar_model_gateway`): internal OpenAI-compatible proxy in front of company-hosted engines. Registry CRUD endpoints are served by `api`. Owns tables `model_providers`, `models`, `model_aliases` ([schema §3](../04-data/schema.md#3-models-ar_domainmodels)). Decision record: [ADR-0005](../02-architecture/adr/ADR-0005-thin-model-gateway.md).

## 1. Responsibilities

1. Expose `/v1/chat/completions`, `/v1/embeddings`, `/v1/rerank`, `/v1/models` (internal only; [internal-apis §2](../05-contracts/internal-apis.md#2-model-gateway-openai-compatible-base-httpmodel-gateway8001)).
2. Resolve `model` = alias → concrete model for the calling tenant (tenant alias overrides platform alias), apply `default_params`, traffic split (canary), and fallbacks.
3. Enforce: model access (tenant may only use its own or platform models), kill switches (`status='disabled'`), quotas (pre-check), concurrency limits per provider (`max_concurrency`), request size (`context_window`).
4. Circuit breakers and health probing per model.
5. Meter every request (`usage_events`) with cost from model prices; emit OTel GenAI spans and Prometheus metrics.
6. Never call an endpoint that is not registered; the namespace has no internet egress (NetworkPolicy).

## 2. Request handling (`/v1/chat/completions`)

1. Verify internal JWT (§[internal-apis §1](../05-contracts/internal-apis.md)); get `tenant_id`, `user_id`, `run_id`, `agent_id`; purpose from `X-AR-Purpose`.
2. Resolve alias: Valkey cache `ar:alias:{tenant}:{alias}` (TTL 30 s, invalidated by `model_alias.updated`) → `ResolvedAlias {primary, fallbacks[], split, default_params}`; unknown alias → 404 `model_alias_not_found` (OpenAI-style error body `{"error":{"message","type":"invalid_request_error","code"}}`).
3. Quota pre-check: `usage.service.check_quota(ctx, metric='model_tokens'|'cost_micros')` reads Valkey counters `ar:q:{quota_id}:{period_key}`; if a `block` quota is exhausted → 429 `quota_exceeded`.
4. Choose target: if `traffic_split` present, weighted random by `run_id` hash (sticky per run). Skip models whose circuit is open.
5. Merge params: request params override `default_params`; strip params the model does not support (e.g. `reasoning_effort` without capability `reasoning`; `tools` without capability `tools` → 400 `model_capability_missing`); force `stream_options.include_usage=true` when streaming.
6. Token guard: estimate prompt tokens (chars/3.5 heuristic, see §6) and reject if `estimate + max_tokens > context_window` → 400 `context_length_exceeded` (the runtime compacts before calling, so this is a safety net).
7. Acquire provider semaphore (`ar:sem:{provider_id}` Valkey-based fair semaphore, slot TTL 15 min) up to 10 s wait; else try the next fallback; else 503.
8. Call upstream with `openai.AsyncOpenAI(base_url=provider.base_url, api_key=<from secret>, timeout=provider.timeout_s)`, `model=upstream_model`.
9. Fallback rule: on connection error, timeout before the first byte, HTTP 429/5xx before the first streamed chunk → record failure, try next fallback (max 2 fallbacks). After the first chunk is sent downstream there is no fallback; a mid-stream error terminates the stream with an SSE error event `{"error":{"code":"upstream_stream_error"}}`.
10. Response header `X-AR-Model-Id`, `X-AR-Fallback-Used: true|false`; in streaming mode the final chunk includes `usage`.
11. Meter (async task, never blocks the response): `usage_events` rows for `model_input_tokens`, `model_output_tokens`, `model_cached_tokens` (from `usage.prompt_tokens_details.cached_tokens` when provided), `cost_micros = in*price_in/1e6 + out*price_out/1e6`; `dedupe_key = mg:{request_id}:{metric}`; increment quota counters.

`/v1/embeddings`: same steps without streaming; batches > 256 inputs rejected (400). Metric `embedding_tokens`. `dimensions` passed only if the model supports Matryoshka (`capabilities` contains `matryoshka`); memory/tool-search callers request `dimensions=1024` when the model's native size differs.

`/v1/rerank`: TEI-compatible body; for `kind='openai_compatible'` providers that expose `/rerank` (vLLM pooling) the same body is forwarded. Metric `rerank_requests`.

## 3. Circuit breaker and health

- Per model, in-process + shared state in Valkey `ar:cb:{model_id}`: closed → open after 5 consecutive failures or ≥ 50 % failures over ≥ 20 requests in 30 s; open for 30 s; half-open allows 1 probe request.
- Health probe loop (every 30 s per provider): `GET {base_url}/models` with 5 s timeout; result stored in `model_providers.health` (written at most once per minute) and gauge `ar_model_provider_up`.

## 4. Registry API (served by `api`)

Permissions: `models:read` (list/get), `models:manage` (write). Platform rows (`tenant_id IS NULL`) are read-only for tenants and managed under `/api/v1/platform/*` by `platform_admin`.

#### GET /api/v1/model-providers
Lists tenant + platform providers. Item `ModelProvider {id, scope: "tenant"|"platform", name, kind, base_url, headers, timeout_s, max_concurrency, status, health}` (API key never returned; `has_api_key: bool`).

#### POST /api/v1/model-providers
Body `{name, kind, base_url, api_key?, headers?, timeout_s?, max_concurrency?}`. `base_url` validation: must be `http(s)`; in SaaS mode hostnames must not resolve to cluster-internal ranges unless the tenant has `isolation_tier != 'shared'` (SSRF guard, `AR_MODEL_PROVIDER_DENY_CIDRS`).

#### PATCH /api/v1/model-providers/{provider_id}
#### DELETE /api/v1/model-providers/{provider_id}
409 if models referenced by aliases.

#### POST /api/v1/model-providers/{provider_id}:test
Probes `GET /models` and returns `{ok, latency_ms, models: [id], error?}`.

#### GET /api/v1/models
Filters `kind`, `provider_id`, `status`. Item `Model {id, scope, provider_id, name, upstream_model, kind, capabilities, context_window, max_output_tokens, embedding_dimensions, price_input_micros_per_mtok, price_output_micros_per_mtok, licence, status}`.

#### POST /api/v1/models
#### PATCH /api/v1/models/{model_id}
Setting `status='disabled'` is a **kill switch**: takes effect within 1 s via cache invalidation; aliases fall back to fallbacks. Audit `model.disabled`.
#### DELETE /api/v1/models/{model_id}

#### GET /api/v1/model-aliases
Effective aliases for the tenant (tenant overrides marked). Item `ModelAlias {id, scope, alias, kind, primary_model_id, fallback_model_ids, traffic_split, default_params, status}`.

#### POST /api/v1/model-aliases
Body `{alias, kind, primary_model_id, fallback_model_ids?, traffic_split?, default_params?}`; validation: models of the same `kind`, visible, active; split weights 0..100 and sum ≤ 100 (remainder → primary). Emits `model_alias.updated`.

#### PATCH /api/v1/model-aliases/{alias_id}
#### DELETE /api/v1/model-aliases/{alias_id}
409 if referenced by published agent versions (via `agent_version_bindings` kind `model_alias`) and no platform alias of the same name exists.

#### POST /api/v1/model-aliases/{alias_id}:test
Permission `models:manage`. Body `{messages: [{role, content}], max_tokens? (≤ 512)}` → `{output, model_id, latency_ms, ttft_ms, usage}` via the gateway (`X-AR-Purpose: test`).

Platform equivalents (role `platform_admin`; same bodies; rows with `tenant_id NULL`):

#### GET /api/v1/platform/model-providers
#### POST /api/v1/platform/model-providers
#### PATCH /api/v1/platform/model-providers/{provider_id}
#### DELETE /api/v1/platform/model-providers/{provider_id}
#### GET /api/v1/platform/models
#### POST /api/v1/platform/models
#### PATCH /api/v1/platform/models/{model_id}
#### DELETE /api/v1/platform/models/{model_id}
#### GET /api/v1/platform/model-aliases
#### POST /api/v1/platform/model-aliases
#### PATCH /api/v1/platform/model-aliases/{alias_id}
#### DELETE /api/v1/platform/model-aliases/{alias_id}

## 5. Configuration (`model-gateway`)

| Variable | Default | Purpose |
|---|---|---|
| `AR_DATABASE_URL` | | Read registry |
| `AR_VALKEY_URL` | | Caches, semaphores, circuit state, quota counters |
| `AR_MG_PORT` | `8001` | |
| `AR_MG_MAX_FALLBACKS` | `2` | |
| `AR_MG_SEMAPHORE_WAIT_S` | `10` | |
| `AR_MG_CB_FAILURES` | `5` | Consecutive failures to open |
| `AR_MG_CB_OPEN_S` | `30` | |
| `AR_MG_HEALTH_INTERVAL_S` | `30` | |
| `AR_MODEL_PROVIDER_DENY_CIDRS` | RFC1918 + link-local + cluster CIDRs (SaaS) | SSRF guard for tenant providers |
| `AR_GUARDRAIL_INPUT_ALIAS` / `AR_GUARDRAIL_OUTPUT_ALIAS` | empty | Optional safety classifier aliases applied for `X-AR-Purpose: agent_step` when the tenant enables `settings.features.guardrails` |

## 6. Token estimation

`ar_common.tokens.estimate(messages, tools) = ceil(len(serialised_json_chars) / 3.5) + 8 * n_messages`. Used for budgeting/guards only; billing uses upstream `usage`. If a model registers `capabilities` containing `tokenize` (vLLM exposes `/tokenize`), the runtime may call `POST {base_url}/../tokenize` via the gateway endpoint `POST /v1/tokenize` (internal, same auth) for exact counts during compaction decisions.

#### (internal) POST /v1/tokenize
Body `{model: alias, messages}` → `{count}`; 404 when unsupported.

## 7. Failure modes

| Failure | Behaviour |
|---|---|
| All targets unavailable | 503 `{"error":{"code":"no_healthy_upstream"}}`; runtime retries the activity (§[spec 07](07-agent-runtime.md) retry policy) and degrades to `fast_alias` after 2 failures if the agent allows (`model.degrade_to_fast: true` default). |
| Upstream returns malformed tool calls | Passed through; the runtime validates (and re-prompts once with a parse-error message). |
| Valkey down | Quota checks fail open with metric `ar_quota_check_bypass_total`; semaphore falls back to in-process limits. |

## 8. Metrics (OpenTelemetry GenAI semantic conventions on spans)

`ar_mg_requests_total{alias,model,purpose,status}`, `ar_mg_ttft_seconds{model}` (histogram), `ar_mg_request_duration_seconds{model}`, `ar_mg_tokens_total{model,direction}`, `ar_mg_fallbacks_total{alias,from,to}`, `ar_mg_circuit_state{model}`, `ar_mg_inflight{provider}`, `ar_model_provider_up{provider}`. Span attributes: `gen_ai.system=openai_compatible`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `ar.tenant_id`, `ar.run_id` (no prompt content on spans).

## 9. Test plan

- Unit: alias resolution precedence; traffic-split stickiness; param stripping; circuit breaker state machine (time-machine); token estimator bounds.
- Integration with `fake-llm` (two instances, one scripted to fail): fallback before first byte; no fallback mid-stream; usage metering rows with dedupe; quota block → 429; kill switch takes effect after invalidation message.
- Load (locust, nightly): 200 concurrent streaming requests against `fake-llm` with 50 ms token delay; gateway overhead p95 < 15 ms added latency to TTFT ([performance budgets](../08-quality/performance-budgets.md)).
