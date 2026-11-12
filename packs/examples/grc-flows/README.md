# GRC flows: how to do each one

These six flows use only the document library, knowledge, agents, and the external API. You don't need any connector.
Test files are in `fixtures/`. Every flow below was run on 5 Nov 2026 against real `Qwen/Qwen3-32B`. See `report.md`.
A refreshed, reproducible, asserting run on current HEAD (SOC 2 + ISO 27001 + CCM, prompt-driven generic actions) is in [`report-2026-11-09.md`](report-2026-11-09.md), driven by `scripts/grc_proof.py` (+ `scripts/grc-login.cjs` for the Keycloak session).

The latest run, on 12 Nov 2026 with the product's own sign-in and eight flows, is in [`report-2026-11-12.md`](report-2026-11-12.md). `scripts/grc_proof.py` now drives that run; the steps below are the earlier walkthrough.

Sign in at `http://127.0.0.1:18132` as `admin@dev.local`.

## A. Policy gap analysis (policy vs SOC 2 / ISO controls)
**In the UI**
1. Go to **Documents → Upload** and add `acme-information-security-policy-v1.md` and `soc2-cc-subset.csv`.
2. Go to **Agents → Create an agent**, name it "GRC Policy Gap Analyst" and select the `documents.read` and `documents.outline` tools.
   Instructions: *"For every control return a table Control | Verdict (met/partial/not_found) | Evidence (section + quote) | Gap. If the policy is silent, the verdict is not_found."* Then **Publish**.
3. Click **Use in chat** and ask: *"Run a gap analysis of policy v1 (document `<id>`) against the control list (document `<id>`)."*

**By API:** `POST /api/v1/conversations {agentId, modelAlias}`, then `POST /api/v1/conversations/{id}/messages {text}`. To check documents directly, call `POST /api/v1/library-documents/{id}:check {requirements:[...]}`.
> Use the agent flow, not the direct **Check** button. Today the direct check only asks the model when the control's wording overlaps the policy's wording. Controls that are worded differently come back `not_found` (see `a-check-endpoint-lexical.png`).

## B. Policy version diff (v1 → v2)
**In the UI:** upload both versions, open v1 in **Documents**, choose **Compare**, pick v2, and you get a section-by-section changed/added/removed view with page anchors.
**By API:** `POST /api/v1/library-documents/{v1}:compare {otherDocumentId: v2, modelAlias}`. The result opens at `/documents/compare?comparisonId=<id>`.

## C. DPA review and redline
1. **Compare:** open the ACME standard DPA and use **Compare** against the vendor DPA. The view shows the missing *Audit* clause, the weakened sub-processor, breach and security clauses, and the added analytics clause.
2. **Review agent:** create a "GRC DPA Reviewer" agent with the documents tools (`compare`, `read`). Ask it to *"review the vendor DPA against our standard, list Art. 28 gaps, propose redlines."*
3. **Propose → accept:** open a clause in the document and choose **Rewrite** with an instruction. That opens **Rewrite review**, where you **Accept** or **Reject** each hunk. Nothing is saved until you accept.
   API: `POST /api/v1/library-documents/{id}:rewrite {anchor, instruction}`, then `POST /api/v1/document-rewrites/{id}:decide {decision:"accept"}`.
> Rewrite only *rephrases* the passage you pick. It refuses to add facts, so it won't paste in the standard clause. Use the agent's chat answer for template redlines.

## D. Vendor questionnaire from your trust library
1. Go to **Knowledge → New collection** "ACME Trust Library" and choose the embedding model `bge-m3`. Add the library documents (policy v2 and the SOC 2 excerpt).
2. Create a "GRC Questionnaire Responder" agent. Attach the collection and the `knowledge.search` tool.
   Instructions: *"answer with [n] citations; if not supported say 'needs owner input'"*.
3. Paste the questionnaire rows from `vendor-questionnaire.csv` into chat. Each answer comes back cited (`[2]`, `[5]` and so on). Questions the documents don't cover, such as ISO 27001 and pen testing, are answered as "not in scope".

## E. Put the GRC agent inside your own product (MCP / REST)
1. Open the agent ("GRC Control Checker"), go to **Expose**, then **Create key**. The full key is shown once; afterwards only the prefix is shown.
2. **MCP:**
```
POST /v1/mcp   Authorization: Bearer <key>
{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"agent_grc_control_checker","arguments":{"message":"Check control CC6.1-MFA against the ACME policy."}}}
```
3. **REST:** `POST /v1/agents/grc-control-checker/conversations`, then `POST /v1/agents/grc-control-checker/conversations/{id}/messages {"text": "..."}`. Add `"stream": true` to get SSE.
   A2A also works: `POST /v1/agents/{slug}/a2a` with `message/send`.

## F. Human approval
Document rewrites are already gated by a person: nothing changes until someone presses **Accept**. They don't go through the **Approvals** queue, and separation of duties (SoD) doesn't apply to them. Writes that do go through **Approvals**, such as HTTP POST or connector writes, need a users-mode approval policy (see `docs/testing/fresh-pass-report.md`).

## Repeat the run
`scripts/grc-start.sh` starts the gateway on 18101, the API on 18131 and the web app on 18132. Then run, in order: `scripts/grc-a.py` (upload, check, compare), `grc-b2.py` (rewrite), `grc-c.py A|C|D` (agents), `grc-e.py` (MCP/REST) and `node scripts/grc-ui.cjs` (screenshots).
The scripts read and write `/tmp/grc-proof/a.json`. They are demo helpers, not product code.
