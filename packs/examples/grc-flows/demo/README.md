# Demo runbook: governance, risk and compliance work on the platform

A live demo of about 20 minutes for a governance, risk and compliance (GRC) audience. Every
step runs on a real install with a real model. Nothing is mocked and nothing on screen is
prepared in advance except the starting content listed below.

The platform has no GRC code. The demo uses the general features (documents, knowledge,
agents, tools, data connections, imported APIs, routines, approvals) on GRC-shaped content.

## What the demo starts from

`scripts/setup_demo.py` and `scripts/setup_watch.py` load this through the public API, as an administrator
would through the screens. The company (Meridian Payments Ltd) and its vendor (CloudLedger
Inc) are invented. `scripts/build_data.py` writes the files in `data/`.

| What | Where it shows |
|---|---|
| Seven documents: the security policy in two versions (3.2 and 4.0), a control list (16 outcomes paraphrased from NIST CSF 2.0), Meridian's standard data processing agreement, CloudLedger's draft of it, CloudLedger's SOC 2 report summary, a customer questionnaire | Documents |
| A knowledge collection, "Meridian policy library", holding policy 4.0 and the standard agreement | Knowledge |
| A risk register in its own Postgres database (18 risks, 12 controls, 8 vendors, 5 scanner findings), connected read-only as `risk_register` | Connections |
| A public API imported from an OpenAPI description: exploit prediction scores (EPSS) from FIRST, as the tool `exploit_scores.vulnerability_score`. One administrator imported it and a second approved it | Tools |
| Three agents: Document analyst, Risk analyst, Third-party risk lead (which hands work to the other two) | Agents |
| The policy watch pack (`packs/examples/policy-watch`): an agent, its source list and a daily routine, installed paused | Agents, Skills, Routines |
| Two people: an administrator and a second administrator who reviews | Settings, Users |

There are no conversations and no runs.

## Before the demo

1. Rebuild the workspace so it has no history (see "On the demo machine" below).
2. Sign in as the administrator in Chrome. Keep a second, private window signed in as the
   reviewer for the approval step.
3. Check the network: the model, `api.first.org` and `www.rbi.org.in` must be reachable.
4. Send one short message to the Assistant so the first model call of the day is not on stage.
   Delete nothing afterwards; one "hello" conversation is fine, or rebuild again.

Each answer takes 20 to 60 seconds; the vendor review takes about two minutes. Talk through
the plan and the tool steps the chat shows while it works. Wording varies from run to run.
The facts below are what every rehearsal run returned.

## The story

### 1. From an empty workspace to a working agent (2 minutes)

- Show **Agents**: two built-in agents and the ones for today. Show **Documents**.
- Press **Create an agent** and type:
  > Create an agent that checks a policy document against a list of controls and reports each gap with the clause it found, and can write the result as a Word report.
- Press **Draft**. Expected in under 30 seconds: a preview with a name (for example "Policy
  Gap Auditor"), instructions and the document tools, and "No blocking errors".
- Point out: the builder is itself an agent; the form and the YAML are there for people who
  want them; nothing is published until a person presses the button.

### 2. Document intelligence and comparison (6 minutes)

Open **Agents**, press **Chat** on **Document analyst**, and ask in turn.

> What changed between version 3.2 and version 4.0 of the Meridian information security policy? Group the changes into: made stricter, added, removed.

Expected: nine clauses made stricter (review cycle, MFA recommended to required, access
review yearly to quarterly, leavers five days to one, logs 90 to 365 days, alerts four hours
to one, scans monthly to weekly, critical fixes 30 days to 7, incident report 72 hours to
24), two additions (yearly vendor re-assessment, a new section on artificial intelligence),
one removal (removable media). It calls `documents.diff`, which compares the text itself and
involves no model, so nothing is invented.

> Check version 4.0 of the Meridian information security policy against the NIST CSF control list in the library. Give a table: control id, verdict (met, partly met, not met), the policy clause that supports it. Then list the gaps.

Expected: 15 of 16 met, each with its clause. One gap: PR.IR-04, capacity planning, which
the policy does not cover. Ask the same of version 3.2 to show nine gaps, so the audience
sees the new version closed eight of them.

> Review CloudLedger's draft data processing agreement against our standard agreement. For each clause where the draft is weaker than ours, say what ours says, what theirs says, and propose the wording to send back.

Expected: the draft's own-use carve-out, "commercially reasonable" security, sub-processors
without consent, breach notice 7 days instead of 48 hours, the missing audit right, data in
any country, deletion in 180 days, the liability cap, the added analytics clause.

> From the CloudLedger SOC 2 report, give me the report period, the auditor, the opinion, and every exception noted with its control.

Expected: 1 October 2025 to 30 September 2026, Northgate Assurance LLP, a qualified
opinion, exceptions on CC6.1 (MFA, 3 of 25 accounts), CC6.3 (review 41 days late) and A1.2
(a failed restore test).

> Answer the customer security questionnaire in the library from our policy library. One row per question: number, answer, source. Where our documents do not say, write 'needs owner input'.

Expected: ten answers with the clause each comes from, and "needs owner input" for ISO
27001 certification and cyber insurance, which no document covers. Follow with "Write that
as a Word document" to get a file to download.

> In CloudLedger's draft data processing agreement, rewrite the breach notification, sub-processor and return-and-deletion clauses to match our standard agreement. Give me the result as a Word document with tracked changes, and leave the original as it is.

Expected: a new version of the draft as a Word file with three tracked changes, downloadable
from the reply, and the original untouched. Open it in Word to accept or reject each change.

The comparison is also on the **Documents** screen, with no question to write: under the
list, choose the earlier and the later document and press **Compare**. It shows how many
sections changed, were added or were removed, and each changed section side by side with the
differing words marked. No model is asked, so it answers at once. Checking and rewriting
are done in chat.

### 3. Data and outside systems (4 minutes)

Show **Connections** (the risk register, read-only) and **Tools** (search "exploit": the
imported API, with who approved it). Then chat with **Risk analyst**.

> Which open risks have no owner? Show the residual score and when each was last reviewed.

Expected: R-012 (20), R-003 (16), R-005 (12). It reads the table list, then writes the SQL.

> Which controls failed their last test, and which risks do they treat?

Expected: C-04 (treats R-004 and R-017), C-01 (R-001), C-09 (R-010).

> For the open vulnerabilities in the register, look up how likely each is to be exploited and rank them. Which should we fix first?

Expected: three open findings ranked by the live score from the public API, with
CVE-2021-44228 on the customer portal first. This is the step that joins the customer's own
database to an outside system in one answer.

To show the import live instead: **Tools**, import an API description, and have the second
administrator approve it. Nobody can approve a tool they submitted.

### 4. Agents working together (3 minutes)

Chat with **Third-party risk lead**.

> We are about to renew CloudLedger Inc. Run a vendor review and tell me whether to approve.

Expected in about two minutes: the lead hands the contract and the SOC 2 report to the
Document analyst and the register to the Risk analyst, at the same time, then writes one
assessment: a recommendation (in rehearsal, "approve with conditions" or "reject as
drafted"), the findings from each specialist with their sources, and the conditions to put
to the vendor. Open **Run details** to show the two child runs.

### 5. Work that runs on its own (2 minutes)

- **Routines**, **Policy watch**: installed from a signed pack, paused until a person turns
  it on. Open its skill, "Policy watch sources", to show that what it watches is a list a
  customer edits, not code.
- Press **Resume**, then **Run now**. It reads the regulator's feed and page, keeps a copy of
  what is new, compares a changed page with the copy before, and looks up the sections of
  the policy library a change touches. A run with nothing new reports nothing, so a daily
  schedule does not fill an inbox.

### 6. Control (2 minutes)

- **Settings**, **Users**: invite a person, suspend a person. A suspended person is shut out
  at once.
- **Approvals** and **Policies**: a tool that writes or sends waits for a person, and the
  person who built an agent cannot approve its actions.
- An agent's page, **Expose**: a key that lets another system call the agent by REST, MCP or
  A2A.
- Close on the point that the customer's own model, data and rules run on their own
  infrastructure.

## What to say if asked

- **Is this built for GRC?** No. The same features serve any document-heavy or data-heavy
  work. GRC-specific products ship as packs a customer installs.
- **Which model is this?** Whatever the customer connects. The demo uses Qwen3.8-27B through
  an OpenAI-compatible endpoint. No answer leaves the customer's install except to that model.
- **The markers like `[p1-s13]`?** The passage of the document a statement rests on.

## Known limits on the day

- The chat labels every agent's reply "Assistant".
- A specialist called by another agent gets 45 seconds unless the lead's definition gives
  more. The demo's lead gives its specialists 300 (`subagents.child_timeout_s`).
- What the agents a lead calls use counts against the lead's own budget. With the default
  budget (80,000 tokens) the vendor review stops before the lead writes its assessment, so
  the demo's lead has a budget of 400,000 tokens. A lead you build yourself needs one sized
  for the agents it calls.
- The model sometimes adds a remark of its own that is not from the documents (in one
  rehearsal it misnamed a CVE). The figures and clauses came from the tools each time.
- Slack, Teams and the other account-based connectors need real accounts and are not part of
  this demo.

## On the demo machine

These scripts are local to the machine and are not in the repository.

```bash
var/grc-demo/reset.sh    # rebuild from an empty database: tenant, model, content
var/grc-demo/up.sh       # start what reset built, keeping its data
var/grc-demo/down.sh     # stop everything the demo started
```

The web app is started separately:

```bash
(cd apps/web && set -a && . ../../var/grc-demo/demo.env && set +a && pnpm dev --port 3210)
```

Open `http://localhost:3210`. The sign-ins are `admin@demo.local` and `reviewer@demo.local`;
their passwords are `AR_ADMIN_PASSWORD` and `AR_SECOND_PASSWORD` in `var/grc-demo/demo.env`.

## On any other install

Start an install, create a tenant with `scripts/seed_tenant.py`, connect a chat model and an
embedding model, load `data/risk-register.sql` into a Postgres server other than the
platform's own, then:

```bash
AR_API_URL=... AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \
AR_SECOND_EMAIL=... AR_SECOND_PASSWORD=... DEMO_RISK_REGISTER_DSN=postgresql://... \
  uv run --no-sync python packs/examples/grc-flows/demo/scripts/setup_demo.py
AR_API_URL=... AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \
  uv run --no-sync python packs/examples/grc-flows/demo/scripts/setup_watch.py
```

Both scripts can be run again. An install that requires signed packs needs
`DEMO_PACK_SIGNATURE` and `DEMO_PACK_KEY_ID` for the second.
