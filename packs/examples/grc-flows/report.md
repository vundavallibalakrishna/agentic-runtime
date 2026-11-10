# GRC flows report: 5 Nov 2026 (IST)

Fresh-seeded tenant on project Postgres **5433** (no wipe this time). HEAD `c94fee9`. Real `Qwen/Qwen3-32B` via DeepInfra (alias `qwenfresh`), embeddings `BAAI/bge-m3`.
Ports: gateway **18101**, API **18131**, web **18132** (`next start`, `.next-fresh`). Nothing was changed on 5432 (jaiho), 6379, 7233, 8000 or 8013. No connectors were used.
Key scan of this folder: **0 hits**. The agent API key appears only as its prefix `f4a3baf6d9e8`.

| Flow | Result | Evidence | Latency |
|---|---|---|---|
| A. Policy gap analysis (agent) | **PASS with caveats** | run `01a1aada-3e0a-7669-b325-28338f0e6b99`. 11 of 12 controls in the table with section evidence (CC6.1 met 2.1/2.2, MFA partial 2.4 "recommended not enforced", CC9.2 partial, MARS-1 not_found). It dropped A.8.13. CC6.3, CC7.2 and P6.3 were judged on redacted text (see defect 1) | 21.7 s |
| A. Direct `:check` endpoint | **FAIL (product gap)** | check `01a1aad7-e5ad-7233-8d3e-f23163fa3be1`: 11 of 12 `not_found`, because the lexical gate (`_MIN_SCORE 0.34`) drops paraphrased controls before the model sees them. The one cited row quotes the wrong sentence | 3.2 s |
| B. Policy v1→v2 diff | **PASS** | comparison `01a1aad8-0fa8-7049-af70-dd1e90e7a49e`: version, access control (14 chars, MFA required, quarterly review, 1 day revoke), logging (90→365 days, daily review), vendor 5.3 added, IR (twice a year, 4 h), backups 35 days. All anchored p1-sN | 10.8 s |
| C. DPA compare | **PASS** | comparison `01a1aad8-484e-763e-be6d-5abe70adf70b`: Audit clause **removed**; security, sub-processor, DSR, breach and deletion weakened; analytics added; governing law changed | 14.5 s |
| C. DPA reviewer agent | **PASS with caveat** | run `01a1aadb-c6b6-739e-a2cb-9938f804d535`: clause table, Art. 28(3)(h) audit gap and sub-processor objection gap, redlines citing standard clauses. It wrongly called governing law "Same" because both countries were redacted to `[LOCATION]` | 55 s |
| C. Propose → accept | **PASS** | rewrite `01a1aad9-30c4-75a6-b251-1db402f46b65` (API accept) and rewrite `rewrite3` accepted **in the UI** (`c-rewrite-proposed.png` → `c-rewrite-accepted.png`). A template-style redline (`01a1aad8-f2cb…`) returned an unchanged proposal, because rewrite only rephrases | 2–4 s |
| D. Questionnaire from knowledge | **PASS** | collection `01a1aadc-b656-7381-807a-cf3428283c6c` (policy v2 + SOC 2 excerpt, bge-m3); run `01a1aadc-fecd-70b5-a4d8-600d74b457b4`: Q1 to Q7 answered with `[n]` citations (MFA, AES-256, TLS 1.2, 365 days, 72 h, quarterly, SOC 2 Type II). Q8 ISO and Q9 pentest were answered honestly as "not in scope". Knowledge passages were **not** redacted | 13.3 s |
| E. MCP + REST embedding | **PASS** | agent `grc-control-checker`. MCP `tools/list` → `agent_grc_control_checker`; `tools/call` CC6.1-MFA → **Met**, §2.4 exact quote (run `01a1aadd-ebe2-7477-8809-c6edbdb5b6bd`). REST `/v1` CC9.2 → **Met**, §5.1 + §5.3. Full JSON is in `evidence.json` → `flowE` | 7.7 s / 9.3 s |
| F. Human approval | **PASS (rewrite gate) / SKIP (SoD)** | Rewrite accept is a person-only gate, but it doesn't use the Approvals queue or SoD. `f-approval.png` and `f-inbox.png` show the queue. SoD on writes was already proven in the fresh pass | n/a |

First try note: the first Control Checker version (`grc-doc-checker`) passed an anchor to `documents.read` and returned not_found. The instructions were tightened to "read the whole document", and the result is above.

## Defects found (not fixed)
1. **PII redaction corrupts GRC evidence (OQ-66, severe for GRC).** `documents.read` tool results are redacted: "90 days" becomes `[DATE_TIME]`, ACME, Ireland and Mars become `[LOCATION]`, control id `P6.3` becomes `[US_DRIVER_LICENSE].3`, and anchors become `[US_DRIVER_LICENSE]`. There is **no working off switch**: `guardrails.apply_result_safety` reads `settings.<section>.pii_redaction`, but `TenantSettings` forbids that key, so `PATCH /api/v1/tenant` returns 500. Fix: add a `security.piiRedaction` setting, and/or exempt the tenant's own library documents and allow-list entity types (DATE_TIME, LOCATION, US_DRIVER_LICENSE produce false positives).
2. **`:check` is a lexical gate.** It uses word overlap ≥ 0.34 before asking the model, and quotes the first sentence of a whole section. Use embeddings or always ask the model on the top-k passages, and quote the matching sentence.
3. **Rewrite can't redline to a template.** The prompt is "rephrase, do not add facts", so a proposal that equals the original gets stored and then shows as `rejected` on accept. Add a "replace with clause from document X" mode.
4. The chat composer shows "Assistant" even when you open an agent conversation (cosmetic).
5. `documents.read` with a section-number anchor returns empty without saying the anchor was invalid.

## Screenshots (1440 px; light, plus dark where `-dark`)
a-documents-library, a-gap-result, a-check-endpoint-lexical, b-policy-diff, c-dpa-compare, c-dpa-redline, c-rewrite-proposed, c-rewrite-accepted, c-rewrite-accepted-api, d-knowledge-collection, d-questionnaire-cited, e-expose-mcp, grc-agents, f-approval, f-inbox.
