# M5 — Policy & approvals

Goal: every tool call gets an OPA decision; risky calls pause the run until a human approves the exact arguments; admins author and simulate policies; standing approvals remove friction for repeated low-risk writes.

Exit criteria: Playwright: agent proposes a W2 call → run shows "waiting for approval" → approver approves in `/approvals` → run resumes and the tool executes once; changing the arguments after approval is impossible (hash mismatch); a W3 approval requires step-up; a deny rule blocks a call with a model-readable reason.

M5-T08 and M5-T09 are required for 1.0. They are not part of the Playwright scenario above.

---

### M5-T01 · Revision 0012 `policy_approvals` and policy service
- **Depends on:** M4-T03
- **Areas:** `ar_domain/{policy,approvals}/{models.py,repository.py}`, `ar_domain/policy/{service.py,bundle.py}`, migration 0012, `ar_api/routers/{policies.py,opa_bundle.py}`
- **Spec:** [spec 09 §3.2, §4](../03-specs/09-policy-approvals.md#4-policy-api), [schema §7](../04-data/schema.md#7-policy-and-approvals-ar_domainpolicy-ar_domainapprovals), [definition-schema](../05-contracts/definition-schema.md), [ADR-0007](../02-architecture/adr/ADR-0007-opa-policy-engine.md)
- **Do:** Tables of schema §7 (append-only `policy_versions`, `approvals.consumed_at`); endpoints `GET/POST /api/v1/policies`, `GET/PATCH/DELETE /api/v1/policies/{policy_id}`, `GET/POST /api/v1/policies/{policy_id}/versions`, `POST /api/v1/policies/{policy_id}:activate`, `:disable`; declarative rule → Rego data compilation (custom Rego only with plan feature `custom_rego`); bundle builder and `GET /internal/v1/opa/bundles/ar.tar.gz` with ETag (rebuilt by the `opa_bundle` outbox subscriber on `policy.activated`/`policy.disabled`/`tool.disabled`).
- **Done when:** activating a version changes OPA decisions within 10 s (OPA polling interval 5 s).
- **Tests:** integration per endpoint; bundle content snapshot; ETag 304.

### M5-T02 · Rego package `ar.policy`
- **Depends on:** M5-T01
- **Areas:** `policies/rego/ar/{policy.rego,jsonpath.rego,policy_test.rego,jsonpath_test.rego}`, `deploy/compose/opa/config.yaml`
- **Spec:** [spec 09 §2–3](../03-specs/09-policy-approvals.md#2-defaults-by-risk-class-no-rule-matched)
- **Do:** Decision `data.ar.policy.decision` implementing defaults by risk class, rule matching (agent, tool, server, risk class, user groups/teams, classification, argument JSONPath conditions, time windows, channel, trigger), combination deny > require_approval > allow > risk default, W3 allow → require_approval, approver selection output, reasons. Python fallback evaluator (spec 09 §3.3) for OPA outages limited to defaults + deny rules.
- **Done when:** `opa test policies/` passes with ≥ 95 % coverage (`opa test --coverage`); Python fallback agrees with Rego on the shared fixture set.
- **Tests:** Rego unit tests; cross-check test running the same fixtures (`policies/fixtures/*.json`) through OPA and the fallback.

### M5-T03 · `mcp-gateway` policy and approval integration
- **Depends on:** M5-T02
- **Areas:** `ar_mcp_gateway/{policy.py,approvals.py,pipeline.py}`
- **Spec:** [spec 08 §5–6](../03-specs/08-tool-registry-mcp.md#6-policy-input-built-by-the-gateway), [spec 09](../03-specs/09-policy-approvals.md), [ADR-0015](../02-architecture/adr/ADR-0015-approval-args-hash.md)
- **Do:** Replace interim `PolicyDecider` with OPA client (`AR_OPA_URL`, timeout `AR_OPA_TIMEOUT_MS`, fail closed with reason `policy_unavailable` when OPA is unreachable, except the R0 built-ins allowed by the fallback evaluator of spec 09 §3.3 / spec 08 §13); build `PolicyInput`; standing-approval matching (spec 09 §6, never W3); approval creation (preview rendering, approver rule, expiry) returning `requires_approval` with `approval` object; verification + single-use consumption with `args_hash`; eval runs never execute W2/W3 (`runs.eval_context`).
- **Done when:** replaying an approval id for a different argument set fails with `approval_invalid`; consumed approvals cannot be reused.
- **Tests:** integration with OPA container; race test: two concurrent executions with the same approval → exactly one succeeds.

### M5-T04 · Approvals service and API
- **Depends on:** M5-T03, M1-T14
- **Areas:** `ar_domain/approvals/service.py`, `ar_api/routers/{approvals.py,standing_approvals.py}`, `ar_system/subscribers/notifications.py`
- **Spec:** [spec 09 §5–7](../03-specs/09-policy-approvals.md#5-approvals-api)
- **Do:** `GET /api/v1/approvals` (inbox: assigned to me, requested by me, all with `approvals:read_all`), `GET /api/v1/approvals/{approval_id}`, `POST /api/v1/approvals/{approval_id}:decide` (approve/reject with comment, `args_hash` echo, step-up for W3, self-approval rules, optional edit-and-approve creates a new approval with new hash), `POST /api/v1/approvals/{approval_id}:cancel`; `GET/POST /api/v1/standing-approvals`, `POST /api/v1/standing-approvals/{standing_approval_id}:revoke` (`approvals:grant_standing`); `approval.requested` → notifications to approvers (in-app + email now; Slack/Teams in M11).
- **Done when:** decision signals the waiting workflow (`approval_decided`); approvals expire per config.
- **Tests:** integration per endpoint; step-up enforcement; self-approval forbidden unless policy allows.

### M5-T05 · Runtime approval and user-input waits
- **Depends on:** M5-T04
- **Areas:** `ar_runtime/workflows/agent_run.py`, `ar_runtime/activities/{expire_approval.py,evaluate_control_tool.py}`, `ar_api/routers/runs.py`
- **Spec:** [spec 07 §2.1–2.2](../03-specs/07-agent-runtime.md#21-loop-normative-pseudocode), [stream-events](../05-contracts/stream-events.md)
- **Do:** `waiting_approval` status with stream events `tool_call.approval_required` / `tool_call.approval_resolved` (domain events `approval.requested` / `approval.decided` are emitted by the gateway/approvals service); wait on `approval_decided` signal or timer → `expire_approval`; on approve re-execute with `approval_id`; on reject feed rejection reason to the model; `input.required` / `input.resolved` events with `user_input` signal and `POST /api/v1/runs/{run_id}:input` (`AR_INPUT_WAIT_TIMEOUT_S`); `input_responses` passed to the gateway.
- **Done when:** a run can wait 24 h (time-skipping test) and resume; cancel during wait cancels the approval.
- **Tests:** Temporal tests (approve, reject, expire, cancel, user input).

### M5-T06 · Policy simulation and policy tests
- **Depends on:** M5-T02
- **Areas:** `ar_domain/policy/simulate.py`, `ar_api/routers/policies.py`
- **Spec:** [spec 09 §4](../03-specs/09-policy-approvals.md#4-policy-api)
- **Do:** `POST /api/v1/policies:simulate` (input: hypothetical tool call or a past `tool_call_id`, optional draft policy version; output: decision, matched rules, reasons, approver); policy `tests` in the definition executed on version creation (failing tests block activation).
- **Done when:** simulating a draft version does not affect live decisions.
- **Tests:** integration; failing embedded test blocks `:activate` with 422.

### M5-T07 · Web: approvals and policies
- **Depends on:** M5-T05, M5-T06
- **Areas:** `apps/web/src/app/(app)/approvals/**`, `apps/web/src/app/(admin)/admin/policies/**`, `apps/web/src/components/chat/ApprovalCard/**`
- **Spec:** [spec 19 `/approvals`, `/admin/policies`](../03-specs/19-web-app.md)
- **Do:** Approvals inbox (tabs, filters, bulk reject), approval detail (agent, user, tool, risk, rendered preview, raw arguments, diff for edits, step-up prompt for W3), inline approval card in chat, standing approvals list/revoke, policy editor (form + YAML/Rego in Monaco, tests, simulate panel, version history, activate).
- **Done when:** M5 exit-criteria Playwright scenario passes.
- **Tests:** Vitest; Playwright scenario; axe.

### M5-T08 · Output sign-off and review queues
- **Depends on:** M5-T07
- **Areas:** `ar_domain/approvals/{reviews.py,signoffs.py}`, `ar_api/routers/reviews.py`, migration `0021_reviews`, `apps/web/src/app/(app)/reviews/**`
- **Spec:** [spec 09 §11](../03-specs/09-policy-approvals.md#11-reviews-and-sign-off), [schema §21](../04-data/schema.md#21-reviews-and-segregation-of-duties-ar_domainapprovals), [ADR-0025](../02-architecture/adr/ADR-0025-output-signoff.md), [spec 19 §10](../03-specs/19-web-app.md)
- **Do:** Tables `review_queues`, `review_items`, `signoffs`. The ten review endpoints in spec 09 §11. Subjects `artifact`, `file`, `message`, `evidence_item`, `run_record`, `agent_card`, `binder`, `pack_record`. Bulk decide at most 100 items, each in its own transaction. Standing approvals are never consulted. Final level requires step-up when `tenants.settings.security.require_step_up_for_signoff` is true. Web pages `/reviews` and `/reviews/[id]`.
- **Done when:** a content change supersedes the item and does not copy prior sign-offs; a hash mismatch on decide returns 409 `content_changed`; the preparer cannot sign.
- **Tests:** integration per endpoint; bulk partial failure; step-up; Playwright queue to sign-off.

### M5-T09 · Segregation of duties
- **Depends on:** M5-T08
- **Areas:** `ar_domain/approvals/sod.py`, `ar_api/routers/sod.py`, `services/mcp_gateway` policy deny path, migration `0022_sod_constraints`
- **Spec:** [spec 09 §12](../03-specs/09-policy-approvals.md#12-segregation-of-duties), [schema §21](../04-data/schema.md#21-reviews-and-segregation-of-duties-ar_domainapprovals)
- **Do:** Enforce the four platform invariants in spec 09 §12 on approvals and sign-offs. Table `sod_constraints` with `kind='conflicting_roles'` only. `POST /api/v1/policies:simulate` adds `sod`. The gateway denies with reason `sod_violation` and audits `sod.violation_blocked`. Endpoints under `/api/v1/sod-constraints` including `:check`.
- **Done when:** the owner of an agent cannot sign that agent's message, artifact, run record or binder, and cannot approve that agent's tool call; a self-granted standing approval returns 422 `sod_self_approval`.
- **Tests:** truth table for the four invariants; simulate returns `sod.violations` without changing the policy decision; gateway integration.
