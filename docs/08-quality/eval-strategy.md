# Evaluation strategy

Evaluations measure agent quality and safety with **real company models**, complementing deterministic tests that use `fake-llm` ([testing-strategy](testing-strategy.md)). The product feature (suites, cases, assertions, `EvalRunWorkflow`, publish gates) is specified in [spec 18 §4](../03-specs/18-observability-eval.md#4-evaluation); this document defines how the platform team and tenants use it.

## 1. Two audiences

| Audience | What is evaluated | Where |
|---|---|---|
| Platform team | Platform prompts (`ar_runtime/prompts/*.md`), context assembly, wrapping, guardrails, memory extraction, judge prompt, default agent templates, model alias changes | Repo `evals/` suites run by CI `eval-gate` and nightly ([ci-cd §2](../07-ops/ci-cd.md#2-jobs)) against staging model endpoints |
| Tenant builders | Their agents (instructions, tools, knowledge) | In-product suites; optional publish gate per agent |

## 2. Repository suites (`evals/`)

| Suite | Kind | Cases (minimum at 1.0) | Purpose |
|---|---|---|---|
| `evals/functional/assistant.yaml` | functional | 60 | General chat, formatting, refusal of out-of-scope, multi-turn |
| `evals/functional/tools.yaml` | functional | 50 | Tool selection, argument quality, error recovery, `tools.search` usage, plan updates |
| `evals/retrieval/knowledge.yaml` | retrieval | 80 over a fixed corpus `evals/corpora/handbook/` (company handbook-style documents, 120 docs) | Retrieval hit rate, citations present and correct, "I don't know" when unanswerable |
| `evals/functional/memory.yaml` | functional | 30 | Extraction add/update/delete/noop correctness, no sensitive-category extraction |
| `evals/functional/subagents.yaml` | functional | 20 | Delegation decisions, result synthesis, budget adherence |
| `evals/redteam/*.yaml` | red_team | 150 | Categories of [prompt-injection §7](../06-security/prompt-injection.md#7-red-team-corpus): indirect injection via tool output/documents/email, exfiltration via links/images, cross-user memory leak, approval bypass, secret disclosure, jailbreak |
| `evals/safety/guardrails.yaml` | safety | 60 | Input/output classifier true/false positive rates |

Case format: the in-product import format (JSONL/YAML, spec 18 `EvalInput` + assertions + `tool_mocks`) so suites can be imported by tenants. The runner for CI is `uv run python -m ar_system.evals.cli run evals/<suite>.yaml --agent-template <name> --model-alias <alias>`, which uses the same scoring code as `EvalRunWorkflow` against an ephemeral tenant.

## 3. Metrics

| Metric | Definition |
|---|---|
| Pass rate | Cases with all assertions passing / cases |
| Retrieval hit@k | Share of retrieval cases whose expected document is in the top-k chunks (k = 8) — from run `retrieval` step data |
| Citation precision | Citations pointing to a document that supports the claim (judge) / citations |
| Unanswerable accuracy | Correct "don't know" on unanswerable cases |
| Attack success rate (ASR) | Red-team cases where the attack goal was achieved (forbidden tool call, exfil URL rendered, secret/other-user data in output) / red-team cases |
| Tool-call accuracy | Expected tool called with matching args / tool cases |
| Cost and latency | Mean `cost_micros`, p95 latency per case |

## 4. Judges

- LLM judge (`llm_judge`, `refusal`, citation precision) uses alias `reasoning` by default with the judge prompt `ar_system/prompts/judge.md` (rubric + JSON `{score, reason}`), temperature 0.
- Judge calibration: `evals/judge-calibration.yaml` (40 human-labelled examples); judge agreement with labels ≥ 85 % required before a judge model/prompt change is accepted.
- Deterministic assertions preferred whenever possible (`tool_called`, `contains`, `json_schema`, `citation_present`).

## 5. Gates

| Change | Required suites | Gate |
|---|---|---|
| Platform prompt / context assembly / wrapping change | all functional + retrieval + red-team | pass rate not lower than baseline by > 2 points per suite; ASR ≤ 2 % and not higher than baseline; must-pass tag `safety` 100 % |
| Model alias retarget (platform) | functional + retrieval + red-team for agents using the alias | same as above; cost/latency deltas reported |
| Guardrail classifier change | safety + red-team | false-positive rate on benign set ≤ 3 %; ASR not higher |
| Release (1.0 and every minor) | all | retrieval hit@8 ≥ 0.85; citation precision ≥ 0.9; unanswerable accuracy ≥ 0.8; tool-call accuracy ≥ 0.9; ASR ≤ 2 % |
| Tenant publish gate (optional per agent) | suites attached to the agent | `GateConfig` (`min_pass_rate` default 0.9, `max_regression_pct` 5, `must_pass_tags` `["safety"]`) ([spec 18 §4.1](../03-specs/18-observability-eval.md#41-concepts)) |

Baselines are stored as the last accepted eval run per suite and model alias (`evals/baselines/*.json` for repository suites, `baseline_eval_run_id` in product).

## 6. Production feedback loop

Thumbs-down feedback (`message_feedback`) is reviewed weekly by builders via `GET /api/v1/feedback`; representative conversations become cases with `POST /api/v1/eval-suites/{suite_id}/cases:from-conversation` (only with the user's share or builder visibility). Langfuse generation content is available for debugging only when the tenant's `settings.observability.capture_content` is on (default off in SaaS, on in single-tenant).

## 7. Cost control

Eval runs record usage like normal runs (`trigger='eval'`) and count against tenant quotas; CI eval jobs use a dedicated platform tenant with a monthly budget alert; per-PR eval-gate runs only the suites touched by the change (path mapping in `evals/gate-map.yaml`), nightly runs everything.
