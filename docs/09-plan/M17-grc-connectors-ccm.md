# M17 — Evidence connectors and continuous control monitoring

Goal: read-only collectors write hashed evidence, and a control test produces a pass or a finding.

Exit criteria: a scripted AWS fixture run captures evidence, links it to a control, records a failing test, and opens a finding that cannot close without a verified evidence item.

---

### M17-T01 · Connector kit
- **Depends on:** M16-T05, M14-T08
- **Areas:** `packs/grc/src/ar_pack_grc/connectors/kit.py`
- **Spec:** [connectors](../10-grc-pack/connectors.md)
- **Do:** Shared cursor loop, backoff on 429, stable `args_hash`, and capture through `records.capture` with `collection_method=tool_call`. Stop at `AR_GRC_CONNECTOR_MAX_PAGES`. Add that variable to `ar_common.settings` and `.env.example` (it is already in the docs catalogue).
- **Done when:** a fixture with more pages than the cap stops at the cap and captures one item per kept page.
- **Tests:** unit cap and hash stability; capture invoked once per kept object.

### M17-T02 · AWS, Azure and GCP collectors
- **Depends on:** M17-T01
- **Areas:** `packs/grc/src/ar_pack_grc/connectors/{aws,azure,gcp}.py`
- **Spec:** [connectors](../10-grc-pack/connectors.md)
- **Do:** MCP servers `grc_aws`, `grc_azure`, `grc_gcp` with the read tools in the P1 table. No write tools. Credentials use the existing secret-ref and OAuth connection model.
- **Done when:** each server's fixture test captures evidence and never calls a mutating HTTP method.
- **Tests:** recorded HTTP fixtures under `packs/grc/tests/fixtures/<slug>/`.

### M17-T03 · Okta, Entra and Google Workspace
- **Depends on:** M17-T01
- **Areas:** `packs/grc/src/ar_pack_grc/connectors/{okta,entra,google}.py`
- **Spec:** [connectors](../10-grc-pack/connectors.md)
- **Do:** Servers `grc_okta`, `grc_entra`, `grc_google` with the P1 read tools. These feeds also supply entitlement rows for M19-T02, stored as evidence plus, when that task has landed, `grc.entitlements`.
- **Done when:** user, factor and role fixtures capture evidence with `source_system` equal to the server slug.
- **Tests:** fixtures; no write methods.

### M17-T04 · GitHub, GitLab, Jira and ServiceNow
- **Depends on:** M17-T01, M16-T05
- **Areas:** `packs/grc/src/ar_pack_grc/connectors/{github,gitlab,jira,servicenow}.py`
- **Spec:** [connectors](../10-grc-pack/connectors.md)
- **Do:** Read tools for all four. Write tools `create_issue` / `update_issue` and `create_record` / `update_record` are W2 and go through policy and approval. A pack workflow stores `issues.external_ref` after the external write succeeds.
- **Done when:** a W2 create waits for approval; a read captures evidence; the external id is stored on the issue.
- **Tests:** fixtures; approval required on write; external_ref round-trip.

### M17-T05 · Control tests, CCM routines, results and findings
- **Depends on:** M16-T04, M17-T01
- **Areas:** `packs/grc/src/ar_pack_grc/{tests.py,findings.py}`, routine `grc-ccm`
- **Spec:** [api](../10-grc-pack/api.md), [agent-templates](../10-grc-pack/agent-templates.md), [prd](../10-grc-pack/prd.md)
- **Do:** Control-test and finding endpoints. Tools `grc.evidence.attach` (W1), `grc.tests.record_result` (W1), `grc.findings.create` (W2). Routine `grc-ccm` runs `control-tester`. `:close` returns 409 `closure_evidence_required` unless `records.verify` succeeds.
- **Done when:** a failing fixture opens a finding; close without verified evidence is refused; a passing test writes `test_results` and no finding.
- **Tests:** Temporal routine; close guard; W2 approval on `grc.findings.create`.

### M17-T06 · Collector and test evals
- **Depends on:** M17-T05, M13-T04
- **Areas:** `packs/grc/evals/{collectors,control-tests}/`
- **Spec:** [10-grc-pack](../10-grc-pack/README.md), [spec 18 §4](../03-specs/18-observability-eval.md#4-evaluation)
- **Do:** Golden suites for the evidence collector and the control tester. Cases assert the evidence hash, the test outcome and that a fail creates a finding. The suite gates pack template publish.
- **Done when:** the suites pass against `fake-llm` scripted tool results and fail when a case omits the evidence hash.
- **Tests:** eval workflow on the pack suites.
