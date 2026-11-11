# 06 — Admin and cost controls

Status: **partial**. Quotas, plan limits, usage events with `cost_micros`, a usage dashboard JSON, ordered model routes and a Valkey circuit breaker are in the product. Nothing routes a cheap question to a smaller model on purpose. Provider cached tokens are metered. The product does not cache prompts itself.

## What already exists

| Piece | Status | Evidence |
|---|---|---|
| Usage events | done | `usage_events` and `usage_daily`, including `cost_micros`. Migration `libs/ar_domain/src/ar_domain/migrations/versions/20261020_0007_usage.py:31-64` |
| Quotas | done | `UsageBook.create` and `assert_run`. `libs/ar_domain/src/ar_domain/usage/service.py:50-91`. API `services/api/src/ar_api/routers/quotas.py` |
| Plan ceiling | done | Implicit quota from `plans.limits.monthly_cost_micros`. `usage/service.py:436-441` and `:620-632` |
| Run start check | done | `start_run` activity calls the usage assert. `services/runtime/src/ar_runtime/activities/start_run.py:16-26` |
| Tool quota | done | Gateway checks quota before the pipeline. `services/mcp_gateway/src/ar_mcp_gateway/pipeline.py:23-28` |
| Per-key cap | done | Stage 11 recorded `api_key_id` and a key cost cap (`docs/09-plan/progress.md`, Stage 11 row). External `take_quota` lives in `libs/ar_domain/src/ar_domain/exposure/runs.py:391-402` |
| Routes | done | Ordered endpoints per tenant, Valkey circuit outside dev and CI. `libs/ar_domain/src/ar_domain/loop/routing.py:1-28` and `:88-89`. Chat calls `routes_for` then `routed_completion`. `chat/service.py:2187-2196` |
| Aliases | done | `model_aliases` with primary and fallbacks. `libs/ar_domain/src/ar_domain/models/tables.py:84-107`. Resolve in `libs/ar_domain/src/ar_domain/models/logic.py` |
| Capabilities | partial | `streaming`, `tools`, `vision` only. `libs/ar_domain/src/ar_domain/models/aliases.py:49`. Speech is area 08 and must add kinds here without a second registry. |
| Gateway | done | Non-fake model names go to `forward_registered`. A fake name is the dev stand-in. Outside dev and CI a missing fake model is 502, not an invented answer. `services/model_gateway/src/ar_model_gateway/main.py:36-76` |
| Cached tokens | partial | `RunUsage.cached_tokens` is recorded when the provider reports them. `libs/ar_contracts/src/ar_contracts/budget.py:28`. No client cache. |
| Overview API | done | Cost, latency, feedback. `libs/ar_domain/src/ar_domain/runs/service.py:40-67` |
| Grafana | partial | `deploy/helm/agentic-runtime/dashboards/ar-usage.json` panels include recorded cost (`ar_run_cost_micros_total`). It is not a latency-by-model board in the product UI. |
| Literal max tokens | partial | `complete_turn` sets 1500 or 800. `chat/service.py:2207-2208`. Area 02 removes those literals because that file is on the run-loop stage. This stage does not edit `chat/service.py` while stage 15 is open. |

## Target architecture

Budgets stay `UsageBook` quotas plus the plan's `monthly_cost_micros`. Routing stays `routes_for` / `routed_completion`. A tenant who wants cheap questions configures an alias whose ordered routes put a small model first, or a route policy `cost` that picks the cheapest healthy route under the quota. The product does not embed LiteLLM.

```mermaid
flowchart LR
  call[complete_turn]
  routes[routes_for]
  policy[Tenant route policy]
  valkey[(Valkey circuit)]
  provider[Tenant model endpoint]
  meter[usage_events]
  quota[UsageBook]
  call --> quota
  call --> routes --> policy --> provider --> meter
  policy --> valkey
```

Route policies, chosen per alias:

| Policy | Behaviour |
|---|---|
| `ordered` | Today's list. First healthy route wins. |
| `cost` | Among healthy routes under their limits, pick the lowest `cost_per_million` the tenant entered. |
| `latency` | Pick the lowest recent latency stored in Valkey, same place as the circuit. |

There is no hidden classifier that downgrades a question because of its words. A wrong downgrade is a quality bug the tenant cannot see. LiteLLM's complexity router is the pattern we are not copying until Bala asks for it. [LiteLLM strategies](https://docs.litellm.ai/docs/router/learn/strategies) include `cost-based-routing` and `latency-based-routing`, which match the two policies above, and also a complexity router, which this stage leaves out.

Caching is the provider's prompt cache. We record `cached_tokens` and we can send the provider's cache hint when the tenant turns it on for a model that supports it. [LiteLLM on provider prompt caching](https://docs.litellm.ai/docs/tutorials/prompt_caching) is explicit that the cache is shared by everyone using those upstream credentials, and that it is a different feature from a proxy response cache. A Valkey cache of full responses would leak one user's answer to another user on the same prefix. This stage does not add that cache.

The admin screen reads `GET /api/v1/observability/overview` and the usage summary that M12 already ships. It adds a model breakdown from `usage_events` (model id, calls, latency, cost, cached tokens). Grafana keeps the cluster view.

## Gaps

1. No route policy other than ordered fallbacks (`routing.py:28`).
2. No tenant-entered price on a model, so "cheapest" cannot be computed without a hard-coded price list. A hard-coded price list is forbidden.
3. No product UI for cost and latency by model. The overview is tenant-wide (`runs/service.py:43-67`).
4. Provider cache hint is not sent. Only the resulting `cached_tokens` are stored.
5. A response cache does not exist, and adding one across users would be unsafe.

## Contracts and API additions

| Addition | Shape |
|---|---|
| Model route | Optional `costPerMillionIn` and `costPerMillionOut` in micros. Optional `policy` on the alias: `ordered`, `cost`, `latency`. Default `ordered`. |
| Usage summary | Additive `byModel: [{modelId, calls, latencyMsP50, costMicros, cachedTokens}]`. |
| Quota | Existing quota object. Document `metric: cost_micros` as the tenant budget. No new quota type if that metric is already allowed by the check constraint. If it is not, an expand migration adds the value. |
| Admin UI | Uses the summary. No new public field beyond `byModel`. |

Prices are tenant data. The seed does not ship a vendor price table.

## Config surface

| Setting | Where | Default |
|---|---|---|
| Monthly budget | Plan `monthly_cost_micros` and a tenant quota | plan limit |
| Route policy | Alias | `ordered` |
| Prices | Route row | unset. `cost` policy skips a route with no price |
| Provider cache hint | Model setting `promptCache` | false |
| Circuit | Existing Valkey keys `ar:model-circuit:{tenant}:{endpoint}` | unchanged |
| Warn threshold | Tenant `usage.warnRatio` | 0.8, using the existing `quota_warning` notification kind |

## Security and observability

- Prices and routes are tenant rows. Cross-tenant 404.
- Keys stay in `SecretStore`. The audit of a fallback records endpoint id and model id, never the key. That is already the Stage 10 rule.
- `byModel` is visible to `usage:read`.
- Metrics already include `ar_run_cost_micros_total` (`ar-usage.json:16`). Add a latency histogram by model id. The model id is the tenant's alias, not the prompt.
- Circuit state stays in Valkey in staging and production (`routing.py:173`).

## Stories

### S16-01 A tenant budget that stops the run

**Acceptance:** A quota on `cost_micros` for the tenant, or the plan's `monthly_cost_micros`, blocks a new run with the existing quota error once the month's sum reaches it. `start_run` and the gateway both see the block. A warning notification fires at `usage.warnRatio`. The chat shows the quota state M12 already has.
**Proof:** contract.

### S16-02 Prices and a cost policy

**Acceptance:** A route can store input and output micros per million. Alias policy `cost` selects the cheapest healthy route that has a price. Policy `ordered` behaves as today. A route with no price is skipped under `cost` and still used under `ordered`. Policy `latency` uses Valkey samples, not process memory, outside dev and CI.
**Proof:** unit for the choice. Contract for the route API.

### S16-03 Model cost and latency on the admin screen

**Acceptance:** The usage screen shows `byModel` for the selected window: calls, p50 latency, cost, cached tokens. Empty, loading and error states exist. The numbers match `usage_events` for that tenant. Another tenant's models are absent.
**Proof:** contract, and the stage visual pass.

### S16-04 Provider prompt-cache hint

**Acceptance:** When `promptCache` is true on a model, the outbound request includes that provider's cache hint and the response's cached token count is stored on `RunUsage.cached_tokens`. When false, the hint is omitted. No response body is written to Valkey.
**Proof:** contract against a recorded upstream. Live only if the configured model reports cached tokens. Otherwise the live step stays pending.

## Risks and questions for Bala

1. **No automatic downgrade.** Cheap versus large is a tenant alias or the `cost` policy, which uses the tenant's prices. Question: do you want a later stage to add a classifier, or is an explicit alias the product?
2. **Who edits prices?** They affect routing. Question: permission `models:manage`, or a narrower new permission?
3. **File fence.** This stage must not edit `chat/service.py` while Stage 15 is in flight. The 1500/800 token literals are Stage 15. If Stage 15 has merged, a follow-up may touch that call site.
