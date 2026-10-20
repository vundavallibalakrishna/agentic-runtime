# PRD 14 — Evaluation

Builders and the platform team measure agent quality and safety with test suites, judges and regression gates. Spec: [spec 18 §4](../03-specs/18-observability-eval.md#4-evaluation), [eval-strategy](../08-quality/eval-strategy.md). Plan: [M13](../09-plan/M13-observability-eval.md).

### US-EVAL-01 · Create a test suite (P0)
As a **builder**, I want a suite of test cases for my agent (inputs, expected behaviour, tool mocks, tags).
- `POST /api/v1/eval-suites` (kind `functional`, `retrieval`, `safety`, `red_team`) and cases with multi-turn inputs, optional files, simulated user attributes/groups, assertions (`contains`, `regex`, `json_schema`, `tool_called`, `tool_not_called`, `citation_present`, `refusal`, `answer_similarity`, `llm_judge`, latency/cost/steps limits, `no_policy_denials`) and tool mocks.
- Import from JSONL/YAML (`cases:import`) with per-line errors.
- Spec: spec 18 §4.1, §4.3. Plan: M13-T03, M13-T05.

### US-EVAL-02 · Run evaluations safely (P0)
As a **builder**, I want to run a suite against the draft or a published version and see results per case.
- `POST /api/v1/eval-suites/{suite_id}:run` starts `EvalRunWorkflow`; results show pass/fail, scores, output, latency, cost and a link to the run; W2/W3 tool calls are always mocked or denied in eval runs (never executed).
- Spec: spec 18 §4.2, §4.4. Plan: M13-T04.

### US-EVAL-03 · Compare with a baseline (P0)
As a **builder**, I want to see regressions versus the previous run.
- Summary with pass rate, mean scores, cost, p95 latency and the list of regressed cases versus `baseline_eval_run_id`.
- Spec: spec 18 §4.2. Plan: M13-T04, M13-T05.

### US-EVAL-04 · Gate publishing on evaluation (P1)
As a **tenant admin**, I want agents to publish only if their gating suites pass.
- Suites with `gate.required` run automatically on publish (`trigger='publish_gate'`); publish completes only when `min_pass_rate`, `max_regression_pct` and `must_pass_tags` are satisfied; the publish dialog shows gate status.
- Spec: spec 18 §4.1–4.2, [spec 05](../03-specs/05-agent-registry.md). Plan: M13-T04.

### US-EVAL-05 · Turn feedback into test cases (P1)
As a **builder**, I want thumbs-down conversations to become regression cases.
- `GET /api/v1/feedback` lists feedback for agents I can edit (content only where I may view it); `cases:from-conversation` creates a case with a default `llm_judge` rubric from the feedback comment.
- Spec: spec 18 §4.3. Plan: M13-T06.

### US-EVAL-06 · Platform red-team and functional suites (P0)
As a **security officer**, I want built-in red-team suites in every tenant and in CI.
- `evals/redteam/` and `evals/functional/` suites are installed into each tenant at provisioning (kind `red_team`) and run nightly in CI against reference models; release gates per [eval-strategy §5](../08-quality/eval-strategy.md#5-gates).
- Spec: spec 18 §4.5. Plan: M13-T04, M14-T07.

### US-EVAL-07 · Gate strict agents on groundedness (P0)
As a **tenant admin**, I want agents that claim strict grounding to fail publish when the groundedness suite fails.
- The suite `evals/golden/groundedness/` applies only when `output.grounding` is `strict`.
- Spec: [spec 18 §4.6](../03-specs/18-observability-eval.md#46-groundedness-grader). Plan: M13-T07.
