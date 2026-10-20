# PRD 10 — Policies & approvals

Every tool call is decided by policy (allow, deny, require approval) based on risk class, agent, user, channel, arguments and time; humans approve risky actions in the web app, Slack or Teams. Spec: [spec 09](../03-specs/09-policy-approvals.md), [definition-schema §7](../05-contracts/definition-schema.md#7-policy-kind-policy), [ADR index](../02-architecture/adr/README.md). Plan: [M5](../09-plan/M05-policy-approvals.md).

### US-APR-01 · Safe defaults by risk class (P0)
As a **tenant admin**, I want sensible behaviour without writing any policy.
- With no matching rule: `R0` allow; `R1` allow (audited); `W1` allow (audited); `W2` require approval by the requester (routine runs: the owner); `W3` deny.
- Agent override `require_approval: always` upgrades `allow` to approval for that tool.
- Before M5 lands, W2/W3 calls are denied (transitional behaviour, [open-questions](../open-questions.md)).
- Spec: spec 09 §2. Plan: M5-T02, M5-T03.

### US-APR-02 · Approve or reject a pending action (P0)
As an **approver**, I want to see exactly what the agent wants to do and approve or reject it.
- The approval card shows agent, tool, risk class, a human-readable preview (`approval_preview`) and full arguments, requester, policy reasons and expiry; `POST /api/v1/approvals/{approval_id}:decide` with `args_hash` binds the decision to those exact arguments (modified arguments → `approval_invalid`).
- Decision is single-use; the run resumes (`tool_call.approval_resolved`) within 2 s of the decision; rejection returns a clear message to the agent.
- Four-eyes rules prevent the requester from approving when required; W3 approvals may require step-up (`security.require_step_up_for_w3`).
- Spec: spec 09 §5. Plan: M5-T04, M5-T05, M5-T07.

### US-APR-03 · Approvals where I work (P0 web; P1 Slack/Teams)
As an **approver**, I want to be notified and decide from the web inbox, Slack or Teams.
- Notification `approval_requested` in-app (and email/Slack/Teams per my notification settings); interactive buttons in Slack/Teams call the same decide endpoint after identity linking; expired approvals cannot be decided.
- Spec: spec 09 §7, [spec 16](../03-specs/16-channels.md), [spec 20](../03-specs/20-notifications-events.md). Plan: M5-T07, M11-T03, M11-T04, M11-T07.

### US-APR-04 · Write policies (P0)
As a **tenant admin**, I want rules such as "external emails from finance need manager approval" or "no production DB writes outside business hours".
- Policies with rules matching tools (glob), risk classes, agents, triggers, channels, user groups/attributes, data classifications, argument predicates (JSONPath subset) and time windows; effects `allow`, `deny`, `require_approval` with approver mode (`requester`, `agent_owner`, `group`, `users`), required approvals, four-eyes, step-up, TTL.
- Combination: deny wins, then require approval (merged requirements), then allow; W3 `allow` is treated as approval with four-eyes.
- Spec: spec 09 §3.1, definition-schema §7. Plan: M5-T01, M5-T02, M5-T07.

### US-APR-05 · Test and simulate before activating (P0)
As a **tenant admin**, I want policy changes tested so that I don't break agents.
- Each policy version carries tests; `:activate` (step-up required) only succeeds when all tests pass; `POST /api/v1/policies:simulate` evaluates a hypothetical call and returns decision, matched rules and reasons; version history allows re-activating an older version.
- Spec: spec 09 §4. Plan: M5-T06.

### US-APR-06 · Standing approvals for routine work (P1)
As a **member**, I want to pre-approve a narrowly scoped repeated action (e.g. posting the daily digest to one channel) so that I'm not asked every time.
- `POST /api/v1/standing-approvals` (requires `approvals:grant_standing`) scoped to tool + agent/routine + argument constraints, with expiry; matching calls are auto-approved and audited (`approval.standing_used`); never applies to `W3`; revocable at any time.
- Spec: spec 09 §5–6. Plan: M5-T04, M10-T04.

### US-APR-07 · Custom Rego for advanced tenants (P1)
As a **security engineer**, I want to add custom Rego rules that can only tighten decisions.
- With plan feature `custom_rego`, a tenant module may add `deny` and `require_approval` rules; it cannot loosen built-in decisions; modules are validated (`opa check`) and tested before activation.
- Spec: spec 09 §3.1 step 6. Plan: M5-T02, M5-T06.

### US-APR-08 · Policy is always enforced (P0)
As a **security officer**, I want no path that bypasses policy.
- All tool calls go through `mcp-gateway`, which calls OPA; when OPA is unavailable calls fail closed except the listed R0 built-ins; every decision is recorded on `tool_calls` and audited.
- Spec: spec 08 §5, §13; spec 09 §3.3. Plan: M5-T03.

### US-APR-09 · Sign off an output (P0)
As an **approver**, I want to attest a statement and a content hash, separately from a tool-call approval.
- A review queue has levels. I cannot sign my own preparation. A changed subject supersedes the item.
- Spec: [spec 09 §11](../03-specs/09-policy-approvals.md#11-reviews-and-sign-off). Plan: M5-T08.

### US-APR-10 · Segregation of duties (P0)
As a **tenant admin**, I want the platform to refuse a sign-off or approval that concentrates the action in one person.
- The preparer is not a signer. Two levels need two people. An agent owner cannot approve that agent's own output. A standing approval cannot be self-granted by the routine owner.
- Spec: [spec 09 §12](../03-specs/09-policy-approvals.md#12-segregation-of-duties). Plan: M5-T09.
