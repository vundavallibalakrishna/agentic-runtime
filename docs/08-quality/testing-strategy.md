# Testing strategy

Principles: test behaviour at the cheapest level that proves it; real dependencies (Postgres + pgvector, Valkey, OPA, Temporal test server; Qdrant for the optional adapter's conformance run) in integration tests — no SQLite or in-memory stand-ins for Postgres; deterministic models via `fake-llm`; every bug fix adds a regression test.

## 1. Test pyramid

| Level | Tool | Location | Runs | What |
|---|---|---|---|---|
| Unit | pytest (+ `pytest-asyncio`, `respx`, `hypothesis`), Vitest | `*/tests/unit`, `apps/web/src/**/*.test.tsx` | every PR (< 5 min) | Pure logic: services with fake repositories, policy input building, context assembly, wrapping, validators, React components with msw |
| Integration | pytest + testcontainers + Temporal `WorkflowEnvironment` | `*/tests/integration` (marker `integration`) | every PR (sharded, < 10 min) | Repositories with RLS, API endpoints via `httpx.AsyncClient(app=…)`, workflows with real activities against containers, gateways with `fake-llm` and test MCP servers |
| Contract | schemathesis, generated-client tests, JSON Schema snapshot | `services/api/tests/contract` | every PR + nightly fuzz | OpenAPI conforms to implementation; stream events match `ar_contracts`; MCP servers conform to the MCP revision |
| Policy | `opa test` | `policies/rego/ar/*_test.rego` | every PR | Every rule branch of policy.rego; coverage ≥ 90 % |
| End-to-end | Playwright + axe | `apps/web/e2e` | main, nightly, PR label `e2e` | User journeys across web, api, workers, gateways with `fake-llm` |
| Evaluation | eval harness ([eval-strategy](eval-strategy.md)) | `evals/` | prompt/model changes, nightly | Agent quality and safety with real company models |
| Performance | Locust | `tests/load` | nightly (short), pre-release (24 h soak) | [performance-budgets](performance-budgets.md) |

## 2. Unit test rules

- Arrange/act/assert, one behaviour per test, names `test_<unit>_<condition>_<expected>`.
- No network; `respx` for httpx; time frozen with `time-machine`; randomness seeded.
- Property tests (`hypothesis`) required for: argument canonicalisation (`args_hash` with RFC 8785), untrusted-content wrapping (no input can close the wrapper or forge a nonce), cursor encoding, cron/rrule validation, PII recognisers, JSON-path policy matching.
- Table-driven tests for the RBAC matrix (from [authn-authz §4](../06-security/authn-authz.md#4-system-roles)) and plan limits.

## 3. Integration test rules

- Fixtures from `ar_testing` ([M0-T12](../09-plan/M00-scaffold.md)): session-scoped containers, per-test database schema reset via transaction rollback or template database clone (`CREATE DATABASE … TEMPLATE`), factories (`TenantFactory`, `UserFactory`, `AgentFactory`, …) that respect RLS by setting tenant context.
- Every endpoint test suite includes: happy path, validation error, permission denied (403), not found, **cross-tenant access returns 404** (never 403, never data), idempotency (where `Idempotency-Key` applies).
- Workflow tests use the time-skipping environment for timers (approval expiry, routine schedules) and assert history determinism with replay tests (`Replayer` over recorded histories in `tests/replay/*.json`, updated deliberately).
- Test MCP servers: `ar_testing.mcp_servers` provides `echo`, `slow`, `huge_result`, `malicious` (returns injection payloads and oversize output), `drifting` (changes its manifest) servers.

## 4. fake-llm

`services/fake_llm` (M0-T07) is a deterministic OpenAI-compatible server used in dev, CI and e2e.

| Endpoint | Behaviour |
|---|---|
| `POST /v1/chat/completions` | Streaming and non-streaming; tool calls; `usage` populated (tokens = whitespace-split count × 1.3, rounded) |
| `POST /v1/embeddings` | sha256-seeded unit vectors of requested dimension (stable per text) |
| `POST /v1/rerank` | Lexical overlap score |
| `POST /v1/tokenize`, `GET /v1/models` | Simple tokenisation; model list from `FAKE_LLM_MODELS` (default `fake-small,fake-large,fake-embed`) |
| `POST /_scripts`, `DELETE /_scripts` | Register/clear scripts for the script set in header `X-Fake-Script-Set` (default set `default`) |

The script set can also come from the URL path: `http://host:port/s/<set>/v1` answers from `<set>`, and the path wins over the header. This lets a store register the server as an ordinary provider of kind `openai_compatible`, with a base URL and an API key and no special header. A tool result is matched by the tool's name, which the server reads from the assistant message that made the call when the tool message has no `name`.

`ar_testing.stand_in` is the way a test uses it. The session fixture `stand_in` starts the server on a free loopback port. `stand_in.script(set, scripts)` loads a script set and `stand_in.connect(store, tenant_id, script_set=...)` registers a provider, a model and the `reasoning` and `fast` aliases through the store's own calls. The turn then runs the real agent loop and tools. A test does not replace the model call in product code and does not rely on an answer written without a model ([M38a](../09-plan/M38a-one-model-path.md), [OQ-94](../open-questions.md)).

Embeddings follow the same rule. Product code has no vector of its own: knowledge and memory call the model the `embed` alias names. `ar_testing.demo.demo_store()` and `serve_demo_tenant()` register the stand-in's embedding and rerank models (`StandIn.connect_embeddings`) on one server shared by the process (`ar_testing.stand_in.shared()`), and a test against a real database saves them with `save_embeddings`, as the Models screen would. The stand-in's vectors are stable for a text and carry no meaning, so a test that needs a passage found relies on shared words or on the stand-in rerank model. A test that mocks HTTP with `respx` lets loopback through (`respx.route(host="127.0.0.1").pass_through()`), and a test that replaces `asyncio.sleep` wraps the replacement in `ar_testing.sleeping.in_this_thread`, because the stand-in serves from another thread of the same process ([M38b-T07b](../09-plan/M38b-real-tenant.md)).

Script format (also used in YAML scenario files `services/fake_llm/scenarios/*.yaml`, loaded at startup, each file = one script set named after the file):

```yaml
- match: {contains: "weather"}            # or {regex: "..."} or {last_tool_result: {tool: "x", contains: "..."}} or {system_contains: "..."}
  respond:
    tool_calls: [{name: "web.fetch", arguments: {url: "https://example.test"}}]
- match: {last_tool_result: {tool: "web.fetch"}}
  respond: {text: "It is sunny.", delay_ms: 20, tokens_per_chunk: 3}
- match: {contains: "fail"}
  respond: {error: {status: 503}}
```

Rules: first matching script wins; `respond.text` supports `{{last_user}}` and `{{last_tool_result}}` templates; `delay_ms` per chunk simulates latency (load tests use 30–60 ms); default script set rules: a message starting with `/tool <name> <json>` returns that tool call, otherwise reply `fake: <last user text>`. Runtime determinism: the same input and script set always yield the same output.

## 5. Frontend tests

- Component tests for every feature component with loading/empty/error states (msw handlers generated from OpenAPI examples).
- Stream rendering tests feed recorded SSE fixtures (`apps/web/src/test/fixtures/streams/*.ndjson`) through `useRunStream`.
- Storybook stories for chat message parts, tool-call cards, approval cards, builder sections; visual regression is not required in v1.

## 6. End-to-end tests

The browser tests start the API through a harness, `services/api/tests/support/e2e_server.py`: the product's own application with no database, given the demo tenant (its people, agents, fixtures and example conversations). The demo tenant is test data, so the harness puts it in, and unit tests build it with `ar_testing.demo` (`demo_store()` for a store, `demo_application()` for the API application). A product store starts with no tenant. The specs sign in with `signInAs(page, email)` (`apps/web/e2e/support/sign-in.ts`), which uses `/api/v1/test/sign-in`; that path exists only in the harness. Unit tests get the demo tenant's identity from `ar_testing` (`demo_application()` plugs it in); scripts that run against a real stack sign in through the identity provider with `scripts/sign_in.py`. A product process never creates it: an API or a worker that cannot reach its database, or finds no tenant in it, serves nobody and tries again ([OQ-99](../open-questions.md)). The run on real services with a real model is the fresh run ([report](../testing/fresh-tenant-2026-11-06/report.md), M38b-T11).

Playwright projects: `chromium` (required), `firefox` (nightly). In CI a failed test is retried up to twice and a test that then passes is listed as flaky, so one slow page does not fail the job ([OQ-95](../open-questions.md)); there is no retry on a laptop. The default wait for an element is ten seconds. Stack: `make dev` (compose + host processes) in CI, `fake-llm` default script set plus `e2e` set. Journeys (each with axe check on visited pages):
1. Login (Keycloak test realm) → select tenant → chat with default agent → streaming answer → feedback.
2. Builder creates agent from template → adds tool and knowledge → test chat (preview) → publish → member uses it.
3. Tool call requiring approval → approver approves from inbox → run resumes; reject path.
4. Upload file → ask question → citation shown; knowledge collection upload → retrieval with citation.
5. Sandbox code execution → artifact produced → download.
6. Routine created → manual run → delivery to inbox notification.
7. Admin: invite user, assign role, create API key, view audit log, verify chain.
8. Memory: remember fact → visible on `/memory` → delete.
9. Slack channel round-trip against the fake Slack API (nightly).
Flaky test policy: a test failing intermittently is quarantined within 24 h with an issue; quarantined tests block release after 7 days.

## 7. Security tests

| Area | Tests | Where |
|---|---|---|
| Tenant isolation | Mandatory isolation suite ([tenancy-isolation §5](../02-architecture/tenancy-isolation.md#5-mandatory-isolation-tests)): every table RLS-covered (introspection test), cross-tenant API access for every resource endpoint (generated from OpenAPI), retrieval store filter builders (pgvector SQL and Qdrant) plus the `RetrievalStore` conformance suite ([spec 10 §10](../03-specs/10-knowledge.md#10-retrievalstore-conformance-suite)), object key prefixes, Valkey key prefixes, sandbox network isolation (kind) | integration + nightly |
| AuthZ | RBAC matrix table test; every router has a permission dependency (introspection test fails on unguarded routes except an explicit public allowlist) | unit |
| Authn/session | CSRF required on unsafe methods; Origin check; cookie flags; session rotation on login/step-up; step-up enforcement on the list in [authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication) | integration |
| Prompt injection | Red-team corpus ([prompt-injection §7](../06-security/prompt-injection.md#7-red-team-corpus)) through `malicious` MCP server and poisoned documents; asserts: no W1+ tool call without policy/approval, no exfiltration URL rendered, wrapper intact | integration + eval |
| Approvals | `args_hash` binding (modified args after approval → `approval_invalid`), self-approval forbidden when configured, expiry, double decision idempotency | integration |
| SSRF | `ssrf_guard` blocks private, link-local, metadata, IPv6-mapped, DNS-rebinding (resolve-then-connect pinning) | unit + integration |
| Sandbox | Escape attempts (mount, ptrace, raw sockets), egress outside allowlist, metadata IP, resource exhaustion (fork bomb, disk fill) are contained | kind nightly |
| Secrets | No secret in logs (log capture scanning for seeded canary secrets), redaction of audit `detail`, encrypted at rest | integration |
| Audit | Every state-changing endpoint writes an audit event (introspection: router mutating methods ↔ audit calls in tests), chain verification, append-only trigger rejects UPDATE/DELETE | integration |
| Dependencies/static | Scanners in [ci-cd §5](../07-ops/ci-cd.md#5-security-scanning) | CI |
| DAST | ZAP baseline and schemathesis fuzz | nightly |

The threat model's verification column ([threat-model §4](../06-security/threat-model.md#4-verification)) maps each threat to these tests.

## 8. Coverage and gates

- Python line coverage ≥ 85 % per project (`ar_domain`, gateways, runtime ≥ 90 %); branch coverage reported. TS ≥ 80 % lines for `src/features` and `src/lib`.
- Coverage may not drop by > 0.5 % on a PR (diff coverage ≥ 90 % for changed lines).
- Gates for merge: all required CI jobs green ([ci-cd §2](../07-ops/ci-cd.md#2-jobs)); for release: e2e green on main, nightly isolation + security suites green, eval gates met ([eval-strategy §5](eval-strategy.md#5-gates)), performance budgets met in the latest load run.

## 9. Test data

Factories only (no shared fixtures with hidden coupling); deterministic sample data with Indian names, phone and ID formats generated by `ar_testing.data` (no Faker dependency); never real personal data. Golden datasets for evals live in `evals/` and are reviewed like code.
