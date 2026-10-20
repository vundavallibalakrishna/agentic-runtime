# Spec 09: Policy and approvals (`ar_domain.policy`, `ar_domain.approvals`, `opa`)

Endpoints served by `api`; evaluation called from `mcp-gateway` and `runtime-worker`; OPA (`opa` deployable) evaluates the Rego entrypoint with tenant rule data served as a bundle by `api`. Owns `policies`, `policy_versions`, `approvals`, `approval_decisions`, `standing_approvals` ([schema §7](../04-data/schema.md#7-policy-and-approvals-ar_domainpolicy-ar_domainapprovals)). Rule DSL: [definition-schema §7](../05-contracts/definition-schema.md#7-policy-kind-policy). Decision: [ADR-0007](../02-architecture/adr/ADR-0007-opa-policy-engine.md), [ADR-0015](../02-architecture/adr/ADR-0015-approval-args-hash.md). PRD: [10-approvals](../01-prd/10-approvals.md).

## 1. Responsibilities

1. Author, version, test, simulate and activate tenant policies (rules DSL; optional custom Rego behind feature flag `custom_rego`).
2. Build and serve the OPA bundle; evaluate decisions (`allow | deny | require_approval`) for every tool call.
3. Approvals: creation (by `mcp-gateway`), inbox, decision (web and channels), multi-approver, four-eyes, step-up, expiry, single use, args binding.
4. Standing approvals (pre-approvals for routines/agents with argument constraints).

## 2. Defaults by risk class (no rule matched)

| Risk class | Meaning | Default decision |
|---|---|---|
| `R0` | Read, non-sensitive | `allow` |
| `R1` | Read, sensitive/personal data | `allow` (audited) |
| `W1` | Write, reversible, self-scoped (own memory, own sandbox, plan) | `allow` (audited) |
| `W2` | Write affecting others / external side-effects (send message, create ticket) | `require_approval`, approvers `{mode: requester}` (routine runs: the routine owner), TTL `tenant.settings.approvals.default_ttl_s` |
| `W3` | Destructive / financial / irreversible | `deny`, unless a matching rule has `effect: require_approval` (then four-eyes is forced and step-up if `security.require_step_up_for_w3`) |

Agent override `require_approval: always` upgrades `allow` to `require_approval` (requester) for that tool.

## 3. Policy evaluation

`ar_domain.policy.service.evaluate(input: PolicyInput) -> PolicyDecision`:

- `PolicyInput` as in [spec 08 §6](08-tool-registry-mcp.md#6-policy-input-built-by-the-gateway).
- `PolicyDecision {decision, reasons: [str], matched_rule_ids: [str], approval: ApprovalRequirement|null, standing_approval_id: uuid|null}`; `ApprovalRequirement {approvers: ApproverRule, required_approvals, four_eyes, step_up, ttl_s, message}`.
- Transport: `POST {AR_OPA_URL}/v1/data/ar/policy/decision` with `{"input": PolicyInput}`; timeout 200 ms (`AR_OPA_TIMEOUT_MS`), 1 retry. Results are **not** cached (inputs include arguments).
- After OPA returns `require_approval`, Python checks standing approvals (§6) and may convert to `allow`.

### 3.1 Combination algorithm (implemented in Rego `policies/rego/ar/policy.rego`)

1. Collect matching rules from all `active` policies of the tenant (`data.tenants[tenant_id].rules`). A rule matches when **all** non-empty match fields match (empty = any).
2. If any matching rule has `effect: deny` → `deny` (reasons = messages of all deny rules).
3. Else if any has `require_approval` → `require_approval`; requirements merged: approvers from the rule with the lowest `priority` value (ties: first by policy name); `required_approvals = max`, `four_eyes = any`, `step_up = any`, `ttl_s = min`.
4. Else if any has `allow` → `allow`, except risk class `W3` where `allow` is treated as `require_approval` with `{mode: requester}`, four-eyes forced (meaning a second person is needed: approvers become `agent_owner`), step-up per tenant setting.
5. Else default by risk class (§2) and agent override.
6. Custom Rego (feature `custom_rego`): module package `ar.tenants.t_<tenant_id_hex>` may define `deny[msg]` and `require_approval[req]`; these are merged as additional deny/require_approval rules (custom Rego can only **tighten**).

Policy rules are compiled into bundle data; argument predicates (`args[]`) are evaluated in Rego using the JSONPath subset, implemented in `policies/rego/ar/jsonpath.rego` with unit tests (`opa test policies/`).

### 3.2 Bundle

- `GET /internal/v1/opa/bundles/ar.tar.gz` (caller `opa`, internal JWT not required: NetworkPolicy + static bearer `AR_OPA_BUNDLE_TOKEN`). Contents: `/ar/policy.rego`, `/ar/jsonpath.rego`, `/data.json` = `{"tenants": {"<tenant_id>": {"rules": [...], "settings": {"require_step_up_for_w3": bool}}}}`, custom tenant Rego modules, `.manifest` with `revision` = sha256 of contents.
- ETag = revision; OPA config polls every 5–15 s. Activation therefore takes effect within ≤ 15 s (UI states this). Kill switches (agents/tools) are separate and immediate.
- Built in-process by `api` from `policies.active_version_id` rows (platform role, all tenants), cached in Valkey `ar:opa:bundle` and rebuilt on `policy.activated|policy.disabled` events.

### 3.3 Fallback evaluator

If OPA is unreachable: `deny` with reason `policy_unavailable` for everything except the R0 built-ins listed in [spec 08 §13](08-tool-registry-mcp.md#13-failure-modes). Metric `ar_policy_fallback_total`.

## 4. Policy API

Permissions: `policies:read`, `policies:manage`.

#### GET /api/v1/policies
Item `Policy {id, name, description, kind, status, priority, active_version: int|null, latest_version: int, updated_at}`.

#### POST /api/v1/policies
Body `{name, description?, kind: "rules"|"rego", priority?, document?: PolicyDefinition.spec, rego?: string}` → creates policy (`draft`) and version 1. `rego` requires feature `custom_rego` and `opa check` passes (compiled via the OPA REST API `PUT /v1/policies/tmp-<uuid>` on a sidecar-free validation call then deleted).

#### GET /api/v1/policies/{policy_id}
Includes the active and latest versions.

#### PATCH /api/v1/policies/{policy_id}
`{name?, description?, priority?}`.

#### DELETE /api/v1/policies/{policy_id}
Only `draft`/`disabled` policies.

#### GET /api/v1/policies/{policy_id}/versions
#### POST /api/v1/policies/{policy_id}/versions
Body `{document | rego}`. Validates; runs embedded tests (`spec.tests: [{name, input: PolicyInput-partial, expect: {decision, rule_ids?}}]`) through OPA with a temporary bundle, stores `test_report {passed, failed: [{name, got}]}`. Versions are append-only.

#### POST /api/v1/policies/{policy_id}:activate
Body `{version}`; version's tests must pass. Sets `active_version_id`, `status='active'`; outbox `policy.activated`; audit `policy.activated` (with hash). Step-up required for session principals ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)).

#### POST /api/v1/policies/{policy_id}:disable
Outbox `policy.disabled`.

#### POST /api/v1/policies:simulate
`policies:read`. Body `{tool_qualified_name, agent_id?, user_id?, trigger?, channel?, args?: object, include_drafts?: [policy_id]}` → builds a `PolicyInput` (user attributes/groups looked up) and evaluates against the active bundle (+ given drafts) → `{decision, reasons, matched_rule_ids, approval, trace: [{policy, rule_id, matched: bool, failed_condition?}]}`.

## 5. Approvals API

Eligibility (`approvals.service.can_decide(user, approval)`): from `approver_rule`:
- `requester` → `approvals.requested_for_user_id`.
- `agent_owner` → agent `owner_user_id` and owner team members with team role `lead`.
- `group` → members of the listed groups, and caller has `approvals:decide`.
- `users` → listed user ids, and caller has `approvals:decide`.
If `four_eyes`, the requester is excluded. Holders of `approvals:read_all` can view all approvals (not decide unless eligible).

#### GET /api/v1/approvals
Query `scope=to_decide` (default: pending approvals the caller can decide) `|requested` (caller's own) `|all` (`approvals:read_all`), `status`, `agent_id`, `risk_class`. Item `ApprovalSummary {id, status, qualified_name, risk_class, agent: {id, name}, requested_for: {id, display_name}, preview: {title, summary}, approvals_received, required_approvals, expires_at, created_at, conversation_id, run_id}`.

#### GET /api/v1/approvals/{approval_id}
Viewers: eligible approvers, requester, `approvals:read_all`. Response `Approval` = summary + `{arguments (eligible approvers and auditors only, else omitted), args_hash, preview: ApprovalPreview, justification, policy_reasons, approver_rule, four_eyes, step_up_required, decisions: [{approver, decision, comment, channel, created_at}], tool: {description, input_schema}}`.

`ApprovalPreview {title, summary, fields: [{label, value}], diff?: {before, after}, links: [{label, url}]}` rendered from `tool_versions.approval_preview` (`PreviewTemplate {title: "Create issue in {{$.project}}", summary?: "...", fields: [{label, path}], diff?: {before_path, after_path}}`; mustache-like `{{$.path}}` substitution only, no logic; values truncated to 500 chars) or, without template, a generic preview (tool title + pretty-printed arguments ≤ 4 KiB).

#### POST /api/v1/approvals/{approval_id}:decide
Eligible approver. Header `Idempotency-Key`. Body `{decision: "approve"|"reject", args_hash, comment?}`. Checks: status `pending`, not expired, `args_hash` equals (else 409 `conflict` reason `args_changed`), step-up (if `step_up_required`: session `step_up_at` within `AR_STEP_UP_TTL_S` (600 s), else 403 with `step_up_required: true` → client calls `POST /api/v1/auth/step-up` and retries). Inserts `approval_decisions`; if reject → `rejected`; if approve count ≥ required → `approved`; on terminal: `decided_at`, signal `approval_decided` to `run-{run_id}` (`AR_TEMPORAL_*`; if the workflow is gone, mark `cancelled`), outbox `approval.decided`, emit `tool_call.approval_resolved` into the run stream (via the runtime on resume), audit `approval.decided`. Response `Approval`.

#### POST /api/v1/approvals/{approval_id}:cancel
Requester (or run cancel). Pending only. Status `cancelled`, signal workflow.

#### GET /api/v1/standing-approvals
`approvals:grant_standing` (own grants) or `tenant:manage` (all). Items `{id, agent, routine, tool, argument_constraints, max_uses, uses, expires_at, revoked_at, granted_by}`.

#### POST /api/v1/standing-approvals
`approvals:grant_standing`. Body `{agent_id? | routine_id?, tool_id, argument_constraints: [{path, op, value}] (same ops as policy args), max_uses?, expires_at (≤ 90 days)}`. Not allowed for `W3` tools (422 `validation_failed`). The granter must be eligible to approve that tool under current policy for the routine owner/agent (checked via simulate). Audit.

#### POST /api/v1/standing-approvals/{standing_approval_id}:revoke
Granter or `tenant:manage`.

## 6. Standing approval matching

For decision `require_approval` with risk ≠ `W3`: find non-revoked, unexpired rows for (`tool_id`, and `routine_id = run.routine_id` or `agent_id = agent.id`) whose every constraint passes on the arguments; atomically `UPDATE ... SET uses = uses + 1 WHERE uses < coalesce(max_uses, 2147483647) RETURNING id`. Success → `allow` with reason `standing_approval:<id>`; audit `approval.standing_used`.

## 7. Approval notifications and channels

Outbox `approval.requested` → `NotificationFanoutWorkflow` ([spec 20](20-notifications-events.md)): in-app notification (kind `approval_requested`) to each eligible approver (capped at 50; group approvals beyond 50 members notify group via channel only), email (if enabled), Slack/Teams DM with **Approve / Reject / Open** buttons when the approver has a `channel_identities` link. Button payload contains `{approval_id, args_hash}`; `channels` posts to `/internal/v1/channels/approval-decisions`; step-up approvals show only "Open in web". Reminders at 50 % of TTL.

## 8. Limits and config

| Item | Default |
|---|---|
| Max active policies per tenant | 100 |
| Max rules per policy | 200 |
| Approval TTL | 60 s .. 7 days |
| Required approvals | 1..5 |
| `AR_OPA_URL` | `http://localhost:8181` |
| `AR_OPA_TIMEOUT_MS` | `200` |
| `AR_OPA_BUNDLE_TOKEN` | secret |
| `AR_STEP_UP_TTL_S` | `600` (defined in spec 01) |

## 9. Metrics

`ar_policy_decisions_total{decision,risk}`, `ar_policy_eval_seconds`, `ar_policy_fallback_total`, `ar_approvals_created_total{risk}`, `ar_approvals_resolved_total{status,channel}`, `ar_approval_time_to_decision_seconds`, `ar_opa_bundle_build_seconds`.

## 10. Test plan

- Rego unit tests (`opa test policies/ -v`) for every combination rule, each argument op incl. `[*]` semantics, time windows across timezones, custom Rego tightening only.
- Python unit: eligibility truth table, preview rendering (escaping, truncation), standing approval constraint matching and concurrent `uses` increments (parallel test).
- Integration: OPA container with bundle from `api`; activation latency ≤ 15 s; decide with wrong `args_hash` → 409; four-eyes; multi-approver (2 of N); step-up enforcement; Slack decision path via `channels` stub; expiry via runtime timer; OPA down fail-closed.
- E2E: W2 tool call in chat → approval card inline → approve → result streamed; reject → model acknowledges.

## 11. Reviews and sign-off

Sign-off is not a tool-call approval ([ADR-0025](../02-architecture/adr/ADR-0025-output-signoff.md)). A review item freezes the statement the signer attests and the SHA-256 of the subject bytes (`content_hash`). Subjects: `artifact`, `file`, `message`, `evidence_item`, `run_record`, `agent_card`, `binder`. Pack records use `subject_type='pack_record'` and store `{pack_id, record_class, record_id}` in `subject_ref`; core checks the hash the pack supplies and does not interpret the pack row.

A queue defines `levels`: an ordered list of `{level, name, role_key, required_count, step_up}`. Level 1 is the reviewer; the last level is the approver. The preparer is `review_items.preparer_principal_id` and is never eligible at any level. Signers at two levels of the same item must be different principals. A decision body echoes `content_hash` and `statement_hash`; a mismatch is 409 `conflict` reason `content_changed`. When the subject bytes change, the service supersedes the item (`status='superseded'`, audit `review_item.superseded`) and the caller must open a new item. Previous sign-offs are not copied.

Delegation (`decision='delegate'`) is one hop, to a user who holds `reviews:decide` and passes SoD (§12). The delegate decides the same level. Standing approvals never satisfy a sign-off and are not consulted.

Step-up is required on a level whose `step_up` is true, and on the final level when `tenants.settings.security.require_step_up_for_signoff` is true (default). API keys cannot decide a step-up level.

Bulk decide (`:bulk-decide`) accepts at most 100 ids. Each item is decided in its own transaction. The response is `{results: [{id, status, error?}]}` and never fails the whole batch because one item failed.

#### GET /api/v1/review-queues
`reviews:read`.

#### POST /api/v1/review-queues
`reviews:manage`. Body `{slug, name, subject_type, levels, statement_template}`. `statement_template` is plain text with `{title}` and `{content_hash}` placeholders only. Audit `review_queue.created`.

#### GET /api/v1/review-queues/{queue_id}
`reviews:read`.

#### PATCH /api/v1/review-queues/{queue_id}
`reviews:manage`. Audit `review_queue.updated`. Does not rewrite open items; they keep the levels they were opened with.

#### DELETE /api/v1/review-queues/{queue_id}
`reviews:manage`. Refused with 409 when items are `pending` or `in_review`. Audit `review_queue.deleted`.

#### GET /api/v1/review-items
Object-level. Query `scope=to_decide|prepared|all`, `status`, `queue_id`. `all` requires `reviews:read`. `to_decide` returns items where the caller is eligible at `current_level`.

#### POST /api/v1/review-items
Any principal who can read the subject. Body `{queue_id, subject_type, subject_id, content_hash, statement_text}`. The server recomputes `content_hash` from the subject and rejects a mismatch (422 `hash_mismatch`). Audit `review_item.created`. Outbox `review_item.requested` notifies eligible level-1 signers.

#### GET /api/v1/review-items/{review_item_id}
Object-level (preparer, eligible signer, `reviews:read`). Includes `signoffs` and `statement_text`.

#### POST /api/v1/review-items/{review_item_id}:decide
Eligible signer at `current_level`, holding `reviews:decide`. Header `Idempotency-Key`. Body `{decision: approve|reject|delegate, content_hash, statement_hash, comment?, delegated_to_user_id?}`. SoD (§12) is applied before the insert. Approve advances the level or sets `signed` when the last level is complete. Reject sets `rejected`. Audit `review_item.decided` and `signoff.recorded`. Outbox `review_item.decided`.

#### POST /api/v1/review-items:bulk-decide
Same permission and body shape, plus `items: [{review_item_id, content_hash, statement_hash}]` and one shared `decision` and `comment`. Per-item results, as above.

## 12. Segregation of duties

Platform invariants, always enforced for approvals and sign-offs, not stored as rows:

1. The preparer of a review item cannot sign it. The requester of a tool-call approval cannot decide it when `four_eyes` is set (already in §5) and cannot decide it when a sign-off chain is used.
2. Two levels of one review item cannot be signed by the same principal.
3. The owner of the agent that produced the subject (`agents.owner_user_id`) cannot sign a review item whose subject is a `message`, `artifact`, `run_record` or `binder` produced by that agent, and cannot decide a tool-call approval for that agent when the decision would approve the call.
4. A standing approval cannot be granted by the routine owner to themselves for a tool the same owner would also execute unattended. Granting a standing approval still follows §6; this invariant adds: `granted_by` must differ from the routine's `owner_user_id` when the standing approval would otherwise let that owner skip approval. Existing rows keep working; new grants that violate this return 422 `sod_self_approval`.

Tenant constraints live in `sod_constraints` (`kind='conflicting_roles'`, `role_a`, `role_b`, `applies_to` `approval` | `signoff` | `both`). A principal who holds `role_a` cannot decide when the preparer or requester holds `role_b`, and the reverse. The seed contains no pairs.

`POST /api/v1/policies:simulate` gains a `sod` object in the response: `{allowed: bool, violations: [{invariant, principal_id}]}`. The decision value is unchanged; simulation reports SoD separately so a policy author sees a call that policy would allow and SoD would block. The gateway blocks execution when SoD fails, with `policy_decision='deny'` and reason `sod_violation`, and audits `sod.violation_blocked`.

#### GET /api/v1/sod-constraints
`sod:manage` or `policies:read`.

#### POST /api/v1/sod-constraints
`sod:manage`. Body `{role_a, role_b, applies_to}`. Audit `sod_constraint.created`.

#### GET /api/v1/sod-constraints/{constraint_id}
`policies:read`.

#### PATCH /api/v1/sod-constraints/{constraint_id}
`sod:manage`. Body `{enabled?, applies_to?}`. Audit `sod_constraint.updated`.

#### DELETE /api/v1/sod-constraints/{constraint_id}
`sod:manage`. Audit `sod_constraint.deleted`.

#### POST /api/v1/sod-constraints:check
`policies:read`. Body `{action: approval|signoff, preparer_principal_id, signer_principal_id, agent_id?, queue_id?, level?}`. Response `{allowed, violations}`. Does not write.
