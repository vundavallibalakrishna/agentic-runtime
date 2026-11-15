# Agentic Runtime — GRC platform review

- Date: 2026-11-15
- Tree reviewed: `df0e45c9` (`main` at the time of this review)
- Scope: architecture and product review for an offline-first GRC deployment. No product code was changed.
- Method: the catalogues, selection path, egress checks and pack history were read from the current tree. Counts below come from `shipped_tools()` and `CONNECTORS` in that tree (79 built-in tools, 24 connectors, 100 connector tools).

This review uses the 2026-10-20 GRC gap analysis as background. That note looked at the specification before M16–M19 were built, and before Stage 2 removed the GRC pack. Section 7 says which of its gaps are still true.

## 1. Verdict

The platform can already do the offline document work a GRC team does by hand: upload policies and control lists, compare versions, judge a document against statements the customer supplies, cite the passage, and keep a hash-chained audit log. That path was run on 12 November 2026 against uploaded files and does not need a connector (`packs/examples/grc-flows/`).

It cannot, today, be the system of record those same customers expect. Frameworks, controls, risks, vendors, findings, campaigns and the `/grc` screens were built and then dropped. Migration `0031` deletes the `grc` schema. `docs/architecture/README.md` states that `/grc` is "Page not found". What remains of that work is the optional `records` pack (seal, hold, binder, guest, AI card, run record) and generic document tools.

Connectors are the wrong shape for the owner's constraint. Most GRC buyers will not send evidence to a vendor API. The catalogue is still a cloud-SaaS list. Two facts make that worse than "optional extras":

1. A connector the tenant has installed and authenticated is still hidden from the model unless the catalogue's global proof label is `live`. Only Email and GitHub are `live`. Okta, Entra, Jira, ServiceNow, AWS, Azure, GCP and S3 never appear in the prompt, including after a successful install.
2. Connector HTTP calls do not use the tenant egress allowlist. `run_http` calls `guard_public` with `allow=["*"]`. Private ranges (`10/8`, `172.16/12`, `192.168/16`, link-local, CGNAT) are always denied. A connector can reach a public SaaS API even when Web access is empty, and it cannot reach the on-prem ServiceNow, mail host or MinIO that an air-gapped customer actually has.

There is no single switch that stops every way data can leave. The tenant allowlist defaults to empty and does stop `general.fetch`, `general.http` and browser navigation. It does not stop a registered model provider, connector calls, knowledge-source fetches, search providers, SIEM webhooks, or port 443 from the pods that sit on the chart's `allow-app` rule.

## 2. What an on-prem GRC customer can do today

A fresh tenant (`python -m ar_domain.bootstrap`) gets an admin, the Assistant, the Builder, an empty model registry and an empty egress allowlist (`TenantSettings.egress_allowlist` defaults to `[]`). It does not get a Helpdesk agent, a fake model, or any connector account.

| Job | Works fully inside the deployment | What it depends on |
|---|---|---|
| Ingest PDF, Office, HTML, text, images | Yes. Bytes stay in the object store. OCR defaults to the local `tesseract` binary. | `documents.ingest`, `documents.ocr`. Cloud OCR engines return `not_live` unless a named secret points at a cloud endpoint. |
| Policy vs control-list gap check | Yes, if the customer uploads the control list. Verdicts quote a stored passage or come back `not_supported` / `not_judged`. | `documents.judge`, `documents.missing`, `documents.read`. No ISO, SOC 2, NIST, PCI or DPDP text ships in the product. |
| Version diff and redline | Yes. Nothing is saved until a person accepts the diff. | `documents.compare`, `documents.rewrite`. Acceptance is a document decision, not the Approvals queue, and segregation of duties does not apply to it. |
| Questionnaire from an approved library | Yes, as retrieval over uploaded documents. There is no answer-library object, owner or expiry. | `knowledge.search` or `documents.search`. Meaning search needs an embedding model the tenant registered. With none, word overlap is used. |
| Spreadsheets, charts, local code | Yes, in the conversation workspace. DuckDB reads the file. The Assistant's `code` and `shell` overrides set `network: false`. | `general.inspect_table`, `general.query_table`, `general.chart`, `general.code`. |
| Schedules | Yes. A routine can run on a cron inside Temporal. | `routines.create`. Delivery to Slack, Teams or email is a separate, outward channel. |
| Audit of platform actions | Yes. Hash-chained audit, approvals on W2/W3 tool calls, segregation of duties on those approvals. | Core. Gateway rows are `tool.called` / `tool.denied` with the tool name, not the prompt. |
| Evidence seal, legal hold, binder, guest, AI card, run record | Only if the tenant installs and enables the signed `records` pack. Routes 404 while it is off. | `packs/records`. Tools: `records.capture`, `records.get`, `records.verify`. |
| Local chat and embedding models | Yes, if the admin registers an OpenAI-compatible, vLLM or TEI endpoint and points the `reasoning` and `embed` aliases at it. Nothing in the product computes a vector itself. | `libs/ar_domain/src/ar_domain/models/embedding.py`. Provider kind is `openai_compatible`, `vllm`, `tei` or `fake`. |
| Local vector store | Yes. Default backend is pgvector in the tenant Postgres. Qdrant is off unless `AR_VECTOR_BACKEND=qdrant`. | `knowledge/book.py`. |
| Control register, risk register, vendor register, findings, CCM, access-review campaigns, incident clocks, framework crosswalk | No product objects. A person can imitate a gap assessment in chat. The result is a message, not a control row. | Removed with schema `grc`. |
| Continuous evidence from cloud or IdP | The HTTP shapes exist. The model cannot call them (section 5). Pointing them at a private address is denied (section 6). | Connectors. |

`tenants.data_residency` defaults to `in` and is returned by the tenant API. No model route, tool or connector reads it. It is a label.

## 3. Tool inventory

Built-in tools are defined in `libs/ar_domain/src/ar_domain/tools/seed_tools.py` and registered by `shipped_tools()` / `seed()`. Connector tools are defined in `libs/ar_domain/src/ar_domain/connectors/catalog.py` (and `catalog_batch.py`, `catalog_stage11.py`) and mounted on the `connectors` server by `_connector_server`. Records tools are defined in `packs/records/src/records_pack/tools.py` and exist only while that pack is mounted.

"Default assistant" means the tool is in `assistant_definition()` (`libs/ar_domain/src/ar_domain/agents/logic.py`). The Builder and the blank, researcher, analyst and support templates start with an empty tool list. A real tenant does not get Helpdesk. No GRC agent template is seeded.

Risk classes: R0 and R1 run without a person. W1 is a local write (a file, a memory, a routine). W2 waits for an approver. The Assistant binds no W2 tool. `general.http` is R1 and asks for approval itself when the method is not GET or HEAD.

### 3.1 Built-in tools (79)

`general.search` is in the Assistant binding and is then removed from the prompt until a search provider is configured (`tools/readiness.py`). `image.ask` is removed until a vision model is set. With both unset, the Assistant offers 29 tools, which is under the 30-tool threshold, so every remaining schema is sent. Turning both on makes 31 tools and switches the turn to search mode (section 4).

| Tool | Risk | Default assistant | Network or auth | What it does |
|---|---|---|---|---|
| `browser.click` | R0 | no | Page host must be allowlisted | Click an element. A link off the allowlist is not followed. |
| `browser.close_tab` | R0 | no | None of its own | Close a tab by index. |
| `browser.download` | R1 | no | Page host must be allowlisted | Save a download as an artifact. |
| `browser.navigate` | R0 | no | Allowlist; other public hosts need approval; private ranges denied | Open a page in the conversation browser. |
| `browser.new_tab` | R0 | no | None of its own | Open a blank tab. |
| `browser.press` | R0 | no | None of its own | Press a key. |
| `browser.save_pdf` | R0 | no | Uses the page already open | Save the page as a PDF artifact. |
| `browser.save_session` | W1 | no | Sealed locally; secret stays out of the prompt | Write the browser session back to its connection. |
| `browser.screenshot` | R0 | no | Uses the page already open | Save a screenshot. |
| `browser.scroll` | R0 | no | None of its own | Scroll the page. |
| `browser.snapshot` | R0 | no | Uses the page already open | Read the page as an accessibility tree. Untrusted. |
| `browser.submit_form` | W2 | no | Submits the page already open | Submit a form. Approval required. |
| `browser.switch_tab` | R0 | no | None of its own | Switch tab by index. |
| `browser.tabs` | R0 | no | None of its own | List tabs. |
| `browser.type` | W1 | no | None of its own | Type into an element. |
| `browser.upload` | W1 | no | None of its own | Attach a workspace file to a file input. |
| `browser.use_connection` | W1 | no | Sealed session; credentials never enter the model | Sign the browser in with a stored connection name. |
| `context.retrieve` | R0 | no | None | Read the rest of a tool result that was shortened. |
| `conversations.search_history` | R1 | no | None | Search this person's earlier messages with this agent. |
| `data.describe_table` | R0 | no | The named database, which can be on-prem | Column names and types. |
| `data.list_schemas` | R0 | no | Same | Schema names. |
| `data.list_tables` | R0 | no | Same | Table names. |
| `data.query` | R0 | no | Same. Read-only SELECT | Rows from one statement. Writes and the platform database are rejected. |
| `documents.compare` | R0 | yes | None | Added, removed and changed passages between two library documents. |
| `documents.create` | W1 | yes | None | Write a DOCX, PDF or XLSX into the workspace. |
| `documents.extract` | R0 | yes | Tenant chat model | Extract named fields. A missing field is null. |
| `documents.ingest` | W1 | yes | None | Parse a file into the library. |
| `documents.judge` | R0 | yes | Tenant chat model | Verdict and quote per statement, rule set, or checklist document. |
| `documents.list` | R0 | yes | None | Library ids, titles, page counts. |
| `documents.missing` | R0 | yes | Tenant chat model | The judge items that are not supported. |
| `documents.ocr` | W1 | yes | Local tesseract. `vision` uses the vision alias. Cloud engines are `not_live` unless a secret is set | Read a scan or image. |
| `documents.outline` | R0 | yes | None | Headings with page and anchor. |
| `documents.read` | R0 | yes | None | Whole text, a page range, or one anchor. Untrusted. |
| `documents.redact` | R0 | yes | Local recogniser | Preview redaction. The original text is not returned. |
| `documents.rewrite` | R0 | yes | Tenant chat model | Propose a diff. Nothing is saved until a person accepts it. |
| `documents.search` | R0 | yes | Embed alias if one is set; otherwise words | Ranked passages with anchors. |
| `documents.summarise` | R0 | yes | Tenant chat model | Summary whose claims cite anchors. |
| `documents.tables` | R0 | yes | None | Tables as CSV. |
| `files.attach_to_sandbox` | W1 | no | None | Copy a conversation file into the working folder. |
| `files.list` | R0 | no | None | Files in the conversation or owned by the person. |
| `files.read` | R0 | no | None | Text of a file by id. |
| `general.chart` | W1 | yes | None | Draw a chart PNG from rows or a workspace sheet. |
| `general.code` | W1 | yes | Off on the Assistant (`network: false`) | Run Python in the working folder. |
| `general.delete` | W1 | no | None | Delete a workspace path. |
| `general.edit_file` | W1 | no | None | Replace an exact string in a workspace file. |
| `general.export_table` | W1 | yes | None | Write CSV or XLSX for download. |
| `general.fetch` | R1 | yes | Allowlist, default empty. Private ranges denied | Fetch a URL's readable text. |
| `general.glob` | R0 | no | None | Workspace paths matching a glob. |
| `general.grep` | R0 | no | None | Regex search of the working folder. |
| `general.http` | R1 | yes | Allowlist, default empty. Non-GET waits for approval | HTTP call. A named connection or secret supplies auth and is not shown back. |
| `general.inspect_table` | R0 | yes | None | Sheets, columns and a sample of a workspace table. |
| `general.list_files` | R0 | yes | None | Working-folder listing. Attachments live under `inputs/`. |
| `general.move` | W1 | no | None | Move or rename inside the working folder. |
| `general.pivot_table` | R0 | yes | None | DuckDB pivot of a workspace sheet. |
| `general.query_table` | R0 | yes | None | One read-only DuckDB statement over workspace files. |
| `general.read_file` | R0 | yes | None | Read a workspace path. |
| `general.search` | R1 | yes, then hidden until a provider is set | Brave or Tavily on the public internet, or SearXNG if the raw setting says so | Web search. Results are untrusted. |
| `general.shell` | W1 | yes | Off on the Assistant | Shell in the working folder. |
| `general.write_file` | W1 | yes | None | Write a text file in the working folder. |
| `image.ask` | R0 | yes, then hidden until a vision model is set | The vision alias's provider | Question about a screenshot, chart or diagram. |
| `knowledge.get_document` | R0 | no | Embed alias only when search embeds | Title and summary, not the full text. |
| `knowledge.list_collections` | R0 | no | None | Collections the person can see. |
| `knowledge.search` | R0 | no | Embed alias if set | Ranked passages the person may read. |
| `memory.forget` | W1 | no | None | Delete one remembered fact. |
| `memory.save` | W1 | no | None | Store a user fact, or an agent note that waits for review. |
| `memory.search` | R0 | no | Embed alias if set | Recall facts this run may see. |
| `research.fetch` | R1 | no | Allowlist. Some fixture pages stay local | Fetch readable text. |
| `research.search` | R1 | no | Same providers as `general.search` | Web search for the research workflow. |
| `routines.create` | W1 | no | The routine later delivers outward if a channel is set | Create a schedule or a webhook URL. |
| `routines.list` | R0 | no | None | List the person's routines. |
| `sandbox.exec` | W1 | no | Retired. A `sandbox` binding is rewritten to `general` | Run a command. The model is not shown this name. |
| `sandbox.export_file` | W1 | no | Retired | Export a workspace file. |
| `sandbox.list_files` | W1 | no | Retired | List the computer workspace. |
| `sandbox.read_file` | W1 | no | Retired | Read the computer workspace. |
| `sandbox.write_file` | W1 | no | Retired | Write the computer workspace. |
| `session.a2a_call` | R1 | no | Allowlist, plus a named secret for the bearer | Call a remote agent card. |
| `session.plan_update` | R0 | yes | None | Replace the visible plan. |
| `session.search` | R0 | yes | None. Embeds tool text if an embed model exists; otherwise words | Find a tool this agent may call. |
| `skills.load` | R0 | no. Added when the agent has skills | None | Load a skill body the prompt only named. |

### 3.2 Records pack (not in the 79)

| Tool | Risk | When it exists | Network | What it does |
|---|---|---|---|---|
| `records.capture` | R1 | Pack `records` enabled | None | Seal text or a file and return the manifest hash. |
| `records.get` | R0 | Same | None | Metadata of one sealed item. Bytes are not returned. |
| `records.verify` | R0 | Same | None | Recompute the hash and say whether it still matches. |

### 3.3 Not in a production catalogue

These exist only when `fake_models_allowed` is true (dev and CI): `web.fetch` (one canned page), `session.checkpoint`, `session.propose_change`, and the demo servers Tickets, Petstore, Warehouse, Desk, Echo and the Revenue analyst agent. `documents.fill_questionnaire` is omitted from the capability matrix because Stage 2 moved it out of core.

### 3.4 Duplicates, dead tools, and tools that assume a network

Duplicates, same job under more than one name:

| Job | Names | What to treat as the real one |
|---|---|---|
| Read or list a working file | `files.read` / `files.list`, `general.read_file` / `general.list_files`, `sandbox.read_file` / `sandbox.list_files` | `general.*` for the workspace. `files.*` for conversation ids. `sandbox.*` is a leftover. |
| Fetch a page | `general.fetch`, `research.fetch`, `browser.navigate`, knowledge source kind `web`, fixture `web.fetch` | `general.fetch`, and only on an agent that is allowed to leave the network. |
| Search | `general.search` and `research.search` (web), `documents.search` and `knowledge.search` (library), `session.search` (tools), `conversations.search_history`, `slack_search` | Keep the library searches on a GRC agent. Web search is a separate, optional tool. |
| Mail | `email_send` / `email_list` / `email_read`, `gmail_*`, `outlook_*` | SMTP/IMAP can be the customer's server. Gmail and Outlook cannot. |
| Object storage | `s3_*` connector, knowledge source kind `s3` | The connector talks to S3 or a compatible endpoint. The knowledge fetcher only reads objects already placed in source config. |
| Files in Microsoft or Google | Connector tools and knowledge kinds `sharepoint`, `confluence`, `google_drive` | Two stacks, two auth paths, neither on the default assistant. |
| Issue trackers | `jira_*`, `servicenow_*`, `zendesk_*`, demo Tickets | Jira and ServiceNow are the GRC-relevant ones. They are hidden from the model. |

Dead or misleading:

- `sandbox.*` is still seeded and the capability matrix marks it offered. `pipeline._bound` rewrites a `sandbox` binding to `general.shell`, `read_file`, `write_file` and `list_files` before the model sees it.
- Cloud OCR names (`google_document_ai`, `aws_textract`, `azure_document_intelligence`) are in the tool schema. The default path returns `not_live`. `documents/ocr_cloud.py` will call an endpoint if the tenant stored one in a named secret.
- The capability matrix says connector tools are "hidden from the model unless live". That is a global badge, not "this tenant connected it". See section 4.

Tools whose description tells the model the internet exists, on the default Assistant:

- `general.fetch` and `general.http` are offered on every offline tenant. The call is refused before any packet when the host is not on the allowlist, and the allowlist starts empty. The refusal is explicit. The selection is not: the model is invited to try.
- `general.search` is withheld until a provider exists, which is the right behaviour. The provider implementation then calls `https://api.search.brave.com` or `https://api.tavily.com`.
- `image.ask` sends the image to whatever provider the vision alias names.

## 4. How a tool is chosen

There is no router and no learned tool policy. Selection is five filters, then the model.

1. **The agent definition.** `definition.tools[]` names a server, a version, and `include` (names or `*`), plus optional overrides such as `allow_hosts`, `timeout_s` and `network`. This is the only place an admin decides the set. It is stored on the published version and is auditable as part of that version.
2. **Catalogue filters** in `ToolPipeline.resolve_catalog` (`tools/pipeline.py`). The server must be approved and not disabled. Clearance above `confidential` is dropped. `offered_to_model` (`proof.py`) drops every `connectors.*` tool whose proof is not `live`. `ready_for` drops `general.search` with no provider and `image.ask` with no vision model.
3. **Context budget.** If the surviving set has more than 30 tools, or `tool_search.mode` is `on`, the loop sends only `files.read`, `files.list`, `session.plan_update`, `session.search` and `skills.load`, plus the tools ranked closest to the user's text (`tool_search.top_k`, default in the 4–32 range). Ranking is the embed alias plus shared words, and words alone when no embed model answers. A tool found by `session.search` has its schema added on the next model call. The choice is logged as `tools_offered` with names only.
4. **The model picks** among the schemas it was sent. `prompts/text/tool_use.md` tells it to choose from the description. There is no deterministic mapping from "gap assessment" to `documents.judge`.
5. **The call is checked again** in `execute`, and in production the worker sends it to mcp-gateway over HTTP. Entitlement, quota, JSON schema, args hash, manifest drift, an eval mock if one is staged, then policy. Policy is OPA when `AR_OPA_URL` is set, otherwise the in-process rules. If OPA does not answer, the fallback allows only `knowledge.search`, `knowledge.get_document`, `knowledge.list_collections`, `memory.search`, `files.list`, `files.read` and `plan.update` (`READ_ONLY_FALLBACK_TOOLS`). A deny rule wins. W2 and W3 wait for an approver who is not the agent owner. The gateway writes `tool.called` or `tool.denied`.

That is explainable for the tools an agent binds, and it is auditable at the version and at the call. It is a weak audit for GRC for three reasons.

- The model is the chooser. A published agent with both `documents.judge` and `general.http` can call either, and the reason is a free-text completion, not a rule.
- Connector visibility is a global proof flag. Installing Okta does not put `okta_list_users` in the prompt. Binding the `connectors` server does put `github_*` and `email_*` in the prompt even when this tenant has no GitHub account and no mailbox. A missing install then returns `connector_not_installed`. A missing OAuth token returns `credential_required` and tells the person to reconnect. Both messages are clear. The model should not have been offered the tool.
- When the set is large, ranking depends on an embedding of the tool text. With no embed model the rank is lexical and the log says so. That is acceptable. It is not a control an auditor can replay unless the embed model id is on the run, which the run record in the records pack is for.

`skills.load` is added whenever the agent has skills, even if the skills server is not bound. The prompt names the skill. The model loads the body. That is a sound split.

Schema size is handled, and the threshold is in the wrong place for the default Assistant. The Assistant binds 31 tools. Offline (no search provider, no vision model) that falls to 29 and the full set is inlined, including fetch and HTTP. Online it crosses 30 and most schemas disappear behind search. The same agent therefore sees a different tool surface because a vision model was added. Connector schemas never dominate the prompt, because 91 of the 100 are hidden. That saves context and hides the tools a connected GRC tenant would actually want.

### Selection rules worth adopting

State these as product rules, and enforce them in `resolve_catalog` rather than in a prompt.

1. A tool is offered only when this tenant can run it now: installed, not disabled, credentials present for anything that needs them, and the host on the allowlist for anything that dials out.
2. The default Assistant binds document, file, table and chart tools only. Fetch, HTTP, web search, browser, A2A and connectors are an explicit "outside this network" binding.
3. Proof (`unit`, `contract`, `live`) stays a badge on the connector page. It does not decide the model's tool list.
4. Above the schema budget, the always-included set for a GRC agent is `documents.judge`, `documents.read`, `documents.search` and `session.search`, not the file tools the Assistant does not bind.
5. The policy fallback, when OPA is down, should include the read-only document tools or refuse the turn. Today it allows a knowledge search and refuses the gap check.

## 5. Connector inventory

The product catalogue is `CONNECTORS` in `libs/ar_domain/src/ar_domain/connectors/catalog.py`. Each row is a definition, not an account. Setup guides are under `docs/11-connectors/`. The screen is `/connectors`.

Class in the table:

- **On-prem possible** — the endpoint is the customer's host. Today a private address is still denied (section 6), so "possible" means the protocol allows it, not that a `10.x` host works.
- **Public SaaS** — the default base URL is a vendor on the internet.
- **OAuth** — needs an authorization-code or client-credentials token from a third party. A bearer or API key pasted by an admin is the other auth kind where listed.

Proof, from `libs/ar_domain/src/ar_domain/proof.py`:

- `live` — a real call was made. Offered to the model.
- `contract` — a recorded public API example was replayed, or the catalogue says `public`. Not offered.
- `unit` — shape and signing were checked, no cassette and no live call. Not offered.

The dispatch matrix (`docs/testing/connector-matrix/report.md`, 100 tools, stub credentials, mock HTTP) reports 6 dispatched, 31 needs-oauth, 57 needs-egress, 6 needs-param, 0 failing. The 6 dispatched are the AWS tools. The 57 "needs-egress" results are the harness calling `stub.example.com`, which the deny list rejects before the mock transport runs. That file proves the gates fire. It does not prove the parsers.

The cassette that does exercise parsers is `libs/ar_domain/tests/fixtures/stage12_connectors.json`, played by a local HTTP server with a sealed fake refresh token (`test_stage12_connector_fixtures.py`). It covers Slack, Drive, Calendar, Gmail, Outlook, SharePoint, Teams, Jira, Confluence, GitHub and REST. No third-party account is required. The same pattern is how the OAuth connectors should be tested.

| Connector | Class | Auth | Proof | Test now | Tools |
|---|---|---|---|---|---|
| Email | On-prem possible (SMTP/IMAP) | Basic | live, against a local SMTP and IMAP stand-in, not a customer mailbox | Extend the stand-in. A private IP is denied | `email_send` W2, `email_list` R0, `email_read` R0 |
| S3-compatible | On-prem possible (custom endpoint) or AWS | Access key | contract. SeaweedFS in a test, not AWS, not MinIO | Local SeaweedFS or MinIO on a host the deny list allows (today: loopback only if `AR_EGRESS_ALLOW_LOOPBACK`) | `s3_list` R0, `s3_get` R0, `s3_put` W2 |
| REST API | On-prem possible | Bearer, API key, or OAuth | contract, recorded example | Point `baseUrl` at the stage12 server | `rest_get` R0, `rest_post` W2 |
| SQL (`data.*` and `connectors/mcp_sql`) | On-prem possible | Connection DSN | unit | A local Postgres. `memory://` is no longer the default when the DSN is missing | `data.list_schemas`, `data.list_tables`, `data.describe_table`, `data.query` |
| OpenAPI import (`connectors/mcp_openapi`) | On-prem possible | Per imported operation | unit | A local spec. `fetch_document` still refuses a private address | Generated operations, not in the 100 |
| GitHub | Public SaaS `api.github.com` | Bearer or OAuth | live. Public read of `octocat/Hello-World`, plus an issue on a repo the proof token could write. Not a customer account | Cassette exists. Live calls need a token and GitHub | `github_list_repos`, `github_list_issues`, `github_list_pulls`, `github_read_file` R0; `github_create_issue`, `github_comment` W2 |
| Slack | Public SaaS | Bearer or OAuth | contract | Cassette | `slack_list_channels`, `slack_read_channel`, `slack_search` R0; `slack_post_message` W2 |
| Jira | Public SaaS unless `baseUrl` is the customer's site | Basic or OAuth | contract. Jira Cloud examples. No site connected | Cassette. A private site is denied | `jira_search` R0; `jira_create_issue`, `jira_update_issue`, `jira_add_comment` W2 |
| Confluence | Same as Jira | Basic or OAuth | contract | Cassette | `confluence_search`, `confluence_read_page` R0; `confluence_write_page` W2 |
| ServiceNow | On-prem possible if the instance URL is public DNS; private IP denied | Basic or OAuth | unit. No instance | No cassette. Add one on the stage12 server | `servicenow_get_incident`, `servicenow_get_change`, `servicenow_query_table` R0; create/update incident and change W2 |
| Teams | Public SaaS, Graph | OAuth or bearer | contract | Cassette | `teams_list_channels` R0, `teams_post_message` W2 |
| Gmail | Public SaaS | OAuth or bearer | contract | Cassette | `gmail_list`, `gmail_read` R0; `gmail_send` W2 |
| Outlook | Public SaaS, Graph | OAuth or bearer | contract | Cassette | `outlook_list`, `outlook_read` R0; `outlook_send` W2 |
| Google Calendar | Public SaaS | OAuth or bearer | contract | Cassette | `gcal_list_events`, `gcal_find_free` R0; `gcal_create_event` W2 |
| Microsoft 365 Calendar | Public SaaS, Graph | OAuth or bearer | unit. No cassette | Copy the Calendar cassette onto Graph shapes | `m365cal_list_events`, `m365cal_find_free` R0; `m365cal_create_event` W2 |
| Google Drive | Public SaaS | OAuth or bearer | contract | Cassette | `gdrive_search`, `gdrive_list`, `gdrive_download` R0; `gdrive_upload` W2 |
| SharePoint and OneDrive | Public SaaS, Graph | OAuth or bearer | contract | Cassette | `sharepoint_search`, `sharepoint_list`, `sharepoint_download` R0; `sharepoint_upload` W2 |
| Notion | Public SaaS | Bearer or OAuth | unit | No cassette | `notion_search`, `notion_read_page`, `notion_read_database` R0; `notion_create_page` W2 |
| Salesforce | Public SaaS | OAuth, client credentials, or bearer | unit | No cassette | `salesforce_query`, `salesforce_get_record`, `salesforce_describe` R0; create and update W2 |
| Zendesk | Public SaaS | Basic or bearer | unit | No cassette | `zendesk_search_tickets`, `zendesk_read_ticket` R0; create and comment W2 |
| HubSpot | Public SaaS | Bearer or OAuth | unit | No cassette | search/read contacts and companies, `hubspot_list_deals` R0; create and update contact W2 |
| Okta | Public SaaS (org host) | Bearer or OAuth | unit. No org | No cassette. This is the one to add first for access-review evidence | `okta_list_users`, `okta_read_user`, `okta_list_groups`, `okta_read_group`, `okta_list_app_users` R0; `okta_deactivate_user` W2 |
| Entra ID | Public SaaS, Graph | Client credentials or OAuth | unit. No directory | No cassette | `entra_list_users`, `entra_read_user`, `entra_list_groups`, `entra_read_group`, `entra_list_apps`, `entra_list_signins` R0 |
| AWS | Public AWS APIs. SigV4 | Access key | unit. Signing matches published examples. No account called | Dispatch matrix hits a mock for all six tools. Not offered to the model | `aws_list_instances`, `aws_describe_instance`, `aws_list_buckets`, `aws_list_iam_users`, `aws_list_iam_policies`, `aws_list_cloudtrail_events` R0 |
| Azure | Public Azure management | Client credentials or bearer | unit. No subscription | No cassette | `azure_list_resources`, `azure_list_resource_groups`, `azure_vm_state`, `azure_list_role_assignments` R0 |
| Google Cloud | Public Google APIs | Service-account JWT (`api_key` in the catalogue) | unit. JWT checked with the public key. No project | No cassette | `gcp_list_projects`, `gcp_list_instances`, `gcp_list_buckets`, `gcp_get_iam_policy` R0 |

### 5.1 Knowledge sources, a second connector stack

`knowledge_sources.kind` is `upload`, `web`, `s3`, `sharepoint`, `confluence`, `google_drive`, `database`, or `mcp_resource` (`knowledge/tables.py`). Upload is local. `web` and the Graph-style kinds call `httpx` from `knowledge/fetchers.py` when `config.url` is set. They do not consult the tenant allowlist. A per-source `allowlist` is checked only for `web`, and an empty one means every host. `fetch_bytes` GETs any `http` URI on an item with no egress check. The S3 knowledge kind reads `config.objects`; it does not call AWS. Database and MCP resource kinds read rows placed in config.

### 5.2 How to test OAuth connectors without live accounts

The stage12 test is the method. Keep using it, and extend the cassette. Do not depend on a vendor sandbox.

1. Start a local HTTP server, as `test_stage12_connector_fixtures.py` does.
2. Install the connector with `baseUrl` pointed at that server.
3. Seal a fake refresh token into the connection the way the OAuth callback would, and serve `POST /token` with a fake access token from the cassette. The test already sets `allow_loopback_token`.
4. Replay a scrubbed public API example for each tool, including the provider's 401 and `missing_scope` bodies. The Slack cassette already has a denied body.
5. Assert the request path, the `Authorization` header shape, and that the token value is absent from the tool result, the audit row and the log.
6. For client-credentials (Entra, Azure, Salesforce) the cassette's token endpoint is the only extra step. No user consent screen is required.
7. For AWS, keep the mock transport in front of the signed request, which the dispatch matrix already does, and add a cassette of the EC2 and IAM response shapes. A live account is still the only way to earn the `live` badge. It is not required to know the parser works.

Missing from the cassette, and worth adding in this order for GRC: Okta, Entra, ServiceNow, AWS response bodies, Azure, then Drive-like sources that are already covered. Salesforce, HubSpot, Zendesk and Notion can wait.

### 5.3 Collectors the October note asked for that are not in the tree

GitLab, Google Workspace admin (users, MFA, admin roles — Drive and Gmail are not that), CrowdStrike, Defender, Intune, Jamf, Tenable, Qualys, HRIS, and a SIEM or Wazuh collector. Regulator feeds (RBI, SEBI, CERT-In, MeitY) are also absent. For an offline-first product that is the right absence. They should not be ported back into core.

## 6. Where data can leave, and the missing switch

The tenant allowlist is the control that exists. It is empty by default. `general.fetch`, `general.http`, browser navigation and `session.a2a_call` refuse a host that is not on it, before the request, and the message tells the admin to add the host under Policies → Web access. An agent override can narrow the list and cannot widen it. `*` is rejected in production. That part is sound.

It is not a kill switch. These paths do not use it.

| Path | What leaves | Stopped by an empty allowlist? |
|---|---|---|
| Chat model | The prompt, documents in context, and tool results. Once an alias points at a registered provider, `_completion_url_for` posts straight to that provider's base URL. The model gateway is only the fallback when no provider is resolved, and the gateway then posts onward with no egress check (`services/model_gateway/.../upstream.py`). | No. The runtime worker's network policy also has no port 443, so a public provider fails closed at the network while the application still tries. The model-gateway, ingest and system-worker pods are on the chart's `allow-app` rule, which allows port 443 to anywhere. An in-cluster model works from the worker only when its port is one the worker may open (8001, 8002, 5432, 6379, 7233, 8200, 8333). |
| Embeddings and rerank | Passage text and queries. `embed()` posts to `{provider}/embeddings` from whichever process asks. | No in application code. Same network-policy split as chat. |
| `image.ask` and OCR `engine=vision` | The image, to the vision provider, by the same direct URL. | No |
| Cloud OCR secret | Page bytes, if `ocr_google`, `ocr_aws` or `ocr_azure` is set. | No |
| Connector HTTP | Evidence and writes. `guard_public(..., allow=["*"])` in `connectors/http.py`. mcp-gateway also has an explicit port 443 egress rule. | No. Private ranges are denied even if the admin listed them |
| Email SMTP/IMAP and S3 custom endpoint | Message bodies and objects. `host_blocked` uses the same private-range deny, not the allowlist. | No for public hosts. Private hosts cannot be enabled |
| Knowledge `web` / Graph fetch | Page and file bytes. | No |
| Web search | The query, to Brave or Tavily. | The tool is hidden until configured. Once configured, the call does not check the allowlist |
| SIEM webhook | Audit events, if `audit.siem.enabled`. | Operator choice, not the allowlist |
| Slack, Teams, email channels | Messages, once a channel is connected. `features.teams_channel` and `features.email_channel` default on; the connection itself does not | No |
| OTEL | Span and metric metadata to `AR_OTEL_EXPORTER_OTLP_ENDPOINT`. Helm points this at the in-cluster collector, which exports to in-cluster Tempo and Loki. Prompt text is not a span attribute. `observability.capture_content` defaults false. | Not phone-home unless the endpoint is changed |
| Sandbox egress | Package mirrors and any host the template allows, intersected with the tenant list when the list is non-empty. The Assistant turns network off for code and shell. | Yes for those two tools |
| Browser stored login | Cookies stay sealed. A scripted login can send a password to the page's host. The host still has to pass the browser allowlist. | Yes |

`deploy/helm/agentic-runtime/values-airgap.yaml` sets a private image registry and `airgap.lockdown: true`. Lockdown adds a network policy that limits the Squid pod to DNS. It does not remove the `allow-app` port 443 rule, does not clear connector base URLs, and does not set a model provider. The API and the runtime worker list internal ports only. Ingest, the system worker, channels, the model gateway and the MCP gateway are not in that tight set. A cloud model call from the runtime worker dies at the network policy. The same call from a process on `allow-app`, or a connector call from mcp-gateway, does not.

`SearchSettings.provider` is `none`, `brave` or `tavily`. SearXNG is implemented in `tools/searching.py` and is the offline search server, and the settings model cannot save it. A stored provider of `none` is truthy, so it also masks `AR_SEARCH_PROVIDER`.

## 7. The October 2026 gap analysis, against this tree

The 2026-10-20 note proposed 11 core tasks and a GRC pack (M16–M19). Progress records those tasks done. Stage 2 and migration `0031` then removed the industry schema, the `/grc` routes and `features.assurance`, and moved the generic records work into `packs/records`. "Closed" below means the capability is still in the tree. "Built then removed" means it landed and is not in the product now.

| October gap or use case | Status now |
|---|---|
| U4 questionnaires, U6 policy drafting, U7 crosswalks as a document exercise | Closed as a document workflow. `documents.judge` / `missing` / `compare` / `rewrite`, citations, customer-supplied control text. No framework catalogue and no crosswalk object. |
| U3 audit prep, U5 vendor risk, U9 risk register, U10 findings, U11 breach clocks, U12 access reviews, U13 attestations, U15 board packs as product objects | Built then removed with schema `grc`. Guests, binders and sign-off primitives survive in the records pack. There is no PBC tracker, vendor, risk, finding, incident or campaign table. |
| U1 continuous control monitoring, U2 evidence collectors | Connector shapes for AWS, Azure, GCP, Okta, Entra, GitHub, Jira and ServiceNow exist and are hidden and mostly untested against a live account. No control-test object, no evidence link, no CCM routine in the product. |
| U8 regulatory change feeds | Still open, and a poor fit for offline. A customer can upload a circular. Nothing polls RBI, SEBI or CERT-In. |
| U14 AI governance of the customer's other models | Partial. The records pack has agent cards, incidents and an export. There is no register of AI systems outside this platform. |
| 1. Evidence vault and chain of custody | Closed in the records pack: sha256, capture, verify, custody via audit. RFC 3161 timestamps were optional and are not a default. |
| 2. Reproducible run records | Closed in the records pack (`run_records`, replay). Opt-in with the pack. |
| 3. Sign-off and segregation of duties | Closed for tool-call approvals (core) and for record sign-off in the pack. Document rewrite acceptance is a separate, weaker gate. |
| 4. GRC domain model and `grc.*` tools | Built then removed. This is the gap that matters. |
| 5. Guest principals | Closed in the records pack (magic link, TOTP, watermark, scoped grant). |
| 6. Legal hold beyond conversations | Closed in the records pack. |
| 7. AI register for this platform's agents | Closed in the records pack. |
| 8. Claim-level grounding | Partial. `documents.summarise` and `documents.judge` cite anchors and refuse an unsupported quote. There is no agent-wide `grounding: strict` that strips every uncited sentence. |
| 9. Binder export | Closed in the records pack (ZIP, hashes, verifier script). No SOC 2 or ISO template, which is correct for core. |
| 10. Curated evidence connectors | Shipped as the catalogue in section 5, then made unreachable by the proof gate and the private-range deny. |
| 11. Classification-based routing to an on-prem model | Still open. `data_residency` is stored and unused. |
| 12. Platform trust pack (ISO 27001 / SOC 2 of the product itself) | Still a docs deliverable, not in this tree. |
| OQ-21 trusted timestamps | Still off. Hash and signature are what the pack does. |
| OQ-23 ship only freely licensed catalogues | Moot while no catalogue ships. Keep this rule when a pack returns. |
| OQ-25 run records opt-in | Holds. The pack is off until installed. |

The October recommendation to keep GRC out of core was right, and the later deletion followed it. The mistake relative to the buyer's constraint is what replaced the pack: a large public-SaaS connector catalogue in core, offered or hidden by a global live flag, with no offline GRC pack beside it.

## 8. Recommendations

Ordered for an offline-first GRC product. Effort is the size of the change: **S** one module and its tests, **M** several call sites or a new policy with tests, **L** a pack (schema, tools, screens, evals).

| # | Action | Why | Effort |
|---|---|---|---|
| 1 | **Fix.** Add one closed-egress mode that every outbound client consults: model gateway, embeddings, connectors, knowledge fetch, search, webhooks, OTEL and the browser. Empty means no outbound except the hosts an admin listed. Helm `airgap.lockdown` should turn this on and drop the model-gateway and mcp-gateway port 443 exceptions. | This is the switch the deployment does not have. The allowlist already works for fetch and HTTP and is ignored by the paths that carry documents. | M |
| 2 | **Fix.** An allowlist entry for a specific host may be a private address. The metadata address and a wide prefix stay denied. | On-prem mail, MinIO, ServiceNow and an internal IdP are in `10/8` or `192.168/16`. Today they are denied even if the admin listed them, while public SaaS is reachable from connectors with `allow=["*"]`. | S |
| 3 | **Fix.** Offer a connector tool when this tenant has it installed, enabled and authenticated. Keep `live` / `contract` / `unit` as a badge. | Installing Okta does nothing for the agent. Binding connectors offers GitHub to a tenant with no GitHub account. | S |
| 4 | **Cut from the default Assistant.** Remove `general.fetch`, `general.http` and `general.search` from `assistant_definition`. Leave them for an agent whose binding opts in. Stop seeding `sandbox.*` into the model catalogue. | An offline tenant is currently invited to fetch the web on every turn. The duplicate computer tools confuse the matrix. | S |
| 5 | **Add a GRC pack, not core tables.** Customer-imported control catalogues (CSV or OSCAL ids the customer is licensed to hold), evidence links into the records vault, a risk and a finding the agent can file through pack tools. Reuse `documents.judge` as the test engine. No ISO or SOC 2 prose in the repo. | The document demo is real. A control row, an evidence hash and an owner are what an auditor asks for next, and they were deleted. | L |
| 6 | **Fix the connector tests.** Extend the stage12 local cassette to Okta, Entra, ServiceNow and the AWS response bodies. Treat `connector_matrix` egress failures as gate tests, not as parser coverage. | OAuth can be tested without a vendor account. The harness for that already exists and covers 11 connectors. | M |
| 7 | **Keep, and make the local path the documented default.** Document tools, tesseract, pgvector, vLLM and TEI provider kinds, the audit chain, approvals and segregation of duties, untrusted wrapping, and the records pack. Put SearXNG on `SearchSettings` so a local search box is a setting, and ship a values snippet whose model URLs are in-cluster. | This is the product that matches the buyer. The pieces are already there. `data_residency` should either force those in-cluster URLs or stop being shown. | M |
| 8 | **Cut from the GRC story.** Salesforce, HubSpot and Zendesk stay available as optional connectors and leave the roadmap. Do not build GitLab, EDR, HRIS or regulator-feed collectors until a named offline customer asks, and then as a pack. | They need public OAuth, they are not offered, and they pull the product toward the deployment these customers refuse. | S |

### What not to do

Do not put framework names, control prose or a `/grc` route back into core. The domain check and Stage 2 exist so the next industry pack can install beside records without a core fork. Do not mark a connector `live` to make the model see it. That badge means a real account was called, and for GitHub it also means the call left the building.
