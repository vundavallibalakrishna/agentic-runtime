# Tool and tool-calling review (5 Nov 2026)

Scope: every tool an agent can call, and the framework that carries a tool call from the model to a result and
back. Read on `main` at `3f6468d`. Nothing was executed for this review; the findings come from the code.

Goal set by the owner: with a strong model, the platform should be as capable as a top coding and
computer-use agent across documents, chat, a real browser, OCR, image generation, and tool choice and chaining.

Each finding is marked **V** (the code was re-read for this review) or **R** (reported by a review pass with a
file reference and not re-read). Paths are under `libs/ar_domain/src/ar_domain/` unless they start with
another top-level folder.

## Verdict

The security spine is sound. Every product path goes through `ToolPipeline`. Arguments are checked against the
tool's JSON schema before policy runs. Policy fails closed when OPA is down. An approval is bound to the
argument hash and is used once. Tool results enter the prompt inside a nonce-tagged untrusted wrapper, after
redaction.

The framework still caps what any model can do. The model reads 2 KB of each result, an approved action ends
the turn, calls run one at a time, and a run stops after eight calls. Of the 163 registered tools, most are
thin, unproven against a live system, or fixtures. A new tool built on this framework inherits the same
limits, so the framework is fixed first ([M38](../../09-plan/M38-tool-framework.md)).

## A. Framework defects

| # | Defect | Where | |
|---|---|---|---|
| A1 | The model sees only the first 2,048 characters of a tool result, cut with "…" and no notice. The pipeline builds the full text up to 64 KB and the loop does not use it. | `tools/logic.py:175`, `tools/agent_loop.py:640`, `tools/pipeline.py:826` | V |
| A2 | After an approval the tool runs and its raw output becomes the final answer. The model does not continue, and the other calls in that step are dropped. `pending_approval` is not persisted, so a restart leaves the run waiting. | `tools/resume.py:47-63` | V |
| A3 | Calls from one model step run one at a time, synchronously, on the event loop. `max_parallel_tool_calls` is not read. A slow call holds every stream in the process. | `tools/agent_loop.py:262,590` | V serial, R blocking |
| A4 | Stop does not stop an in-process run on a real model. The cancel flag is read only in the fake-token loop. Under Temporal the signal works and partial text is lost. | `chat/service.py:1750,2219` | V |
| A5 | The defaults are 8 steps, 8 tool calls and 120 seconds. The definition schema says 30, 60 and 1,200. Model output is fixed at 1,500 tokens when tools are present. | `tools/agent_loop.py:63-69`, `chat/service.py:1912`, `docs/05-contracts/definition-schema.md` | V |
| A6 | Malformed tool arguments become `{}` without a message. Text the model writes beside a tool call is discarded. `finish_reason` is not read, so a cut-off call looks like a schema error. | `models/logic.py:139`, `tools/agent_loop.py:261` | V |
| A7 | The tool-use guidance and the output-schema instruction do not reach the model on the chat path. A prepared prompt replaces them. | `workspace/turn.py:57-59`, `tools/agent_loop.py:150-155` | V |
| A8 | Three built-in tools read across tenants. `conversations.search_history` scans every message. `control.search` ranks every tenant's tools. `files.list` names every tenant's files and `files.read` returns any blob by id; `files.*` is entitled without a binding. | `tools/handlers.py:210-246,343-369`, `tools/pipeline.py:569-574` | V |
| A9 | A handler exception is not caught. The run can stay `running`, or a Temporal retry replays tools that already ran. | `tools/handlers.py:28` | R |
| A10 | A write can run twice. The MCP client retries after a timeout, Temporal retries the whole turn, and the stored idempotency key is not checked. | `tools/remote_mcp.py:257-266`, `tools/pipeline.py:779` | R |
| A11 | Nothing is compacted inside a turn. A context-overflow error is retried as if transient. The window defaults to 8,000 tokens and does not come from the model row. | `memory/session.py:130`, `tools/agent_loop.py:196-211` | R |
| A12 | Every bound tool is sent on every model call. A repeated identical call is not detected. | `tools/agent_loop.py:117,140` | R |
| A13 | `mcp-gateway` is not on the call path. Tools run in the API process. Never-skip rule 4 says otherwise. | `services/mcp_gateway/` | R |
| A14 | Fixtures are in the product catalogue: `control.checkpoint`, `control.propose_change`, a canned `web.fetch`, and the demo servers. The dev and CI gate is set only by the API and defaults to on, so workers seed them. | `tools/handlers.py:254-331`, `chat/service.py:155` | V gate, R rest |
| A15 | The MCP client opens a new session for each call, ignores `tools/list` pagination, and keeps only the first text block of a result. | `tools/remote_mcp.py:185,224,293` | R |

## B. What the tools can do

163 tools are registered: 67 built-in, 92 across 21 connectors, and 4 that the loop adds for agent calls.

| Area | Today | Missing |
|---|---|---|
| Browser | An HTML parser over `httpx`, labelled `engine: fixture`. Links, typed fields, a form POST and a cookie jar work. `screenshot` returns a fixed chart image (V, `sandboxes/runtime.py:437`). | JavaScript, client-rendered sites, real screenshots, uploads, downloads, tabs |
| Code and shell | A host subprocess where the kernel refuses user namespaces. The module says that fallback "is not a security boundary" (V, `libs/ar_common/src/ar_common/isolate.py`). The sandbox image holds curl, git and jq (V, `images/sandbox/Dockerfile`). The container path is not wired. | Isolation on such hosts, data and document libraries, one workspace in place of `general.*` and `sandbox.*` |
| Workspace files | read, write, list | edit, search by content, search by name, move, delete |
| PDF | Text through pypdf. Created PDFs use one Latin font and at most 30 pages. | Tables, layout, merge, split, forms. Scanned pages are read only when the page image is a JPEG stream. |
| Excel and CSV | DuckDB queries over at most 5,000 rows. XLSX is written without formulas, charts or styles. | Formulas read or written, charts, larger data |
| PowerPoint | Slide text is read. One chart slide can be made. | Authoring a deck |
| DOCX | Read. Simple create. A rewrite updates the library copy and not the file. | Edit in place, tracked changes, comments |
| OCR | Local tesseract, English | Other languages, rasterising a page before OCR |
| Vision | `image.ask` works when a vision model is registered. The seeded alias points at the fake model. Images do not enter the chat turn. | The model looking at a page or a screenshot itself |
| Image generation, audio, video, archives, diagrams | None | All of it |
| Web | `general.fetch` is real. `general.search` supports Brave and Tavily and has not been called live. | A live proof, and a self-hosted search option |
| Connectors | Email, S3 and GitHub were called live against stand-ins or a proof token. | 18 connectors have not been called live |
| Knowledge and tool search | Default embeddings are hash vectors. | Ranking that means something before an embedding model is set |
| Skills | Chosen by keyword overlap before the turn. `skills.load` exists and no default agent binds it. | The model choosing a skill |

## C. Tool choice, measurement and what the person sees

- No parameter in `tools/seed_tools.py` has a description. The file has one enum. Arrays have no item schema.
  The weakest are `browser.press`, `browser.scroll`, `browser.type` and `browser.screenshot`, which share one
  `{ref, text}` schema, then `records.*` and `sandbox.*`.
- The eval gym's 12 of 12 was scored with a scripted stand-in for the model. No live score is recorded. No task
  needs two tools. The platform eval runner echoes its input and does not run the agent.
- In chat, nothing shows while a tool runs. Arguments and error detail are hidden. An approval cannot be
  decided inline. The run trace shows a status and nothing else. Answers arrive whole, not as tokens.

## D. Test doubles in product code

Added after the owner asked why a fake model is in the execution path. A second pass found that a gate is not
enough, because several scripted paths run in any environment.

| # | Finding | Where | |
|---|---|---|---|
| D1 | Every store is seeded with a `fake-llm` provider, three `fake-*` models and five aliases. `environments.md` says the fake provider is refused in `prod`; no code refuses it. | `chat/service.py:262-300`, `seed/m2.py:26-49` | V |
| D2 | A turn whose text contains `slow` returns twelve canned sentences. A model call that returns nothing becomes `fake: <the question>`. | `chat/service.py` `_tokens` | V |
| D3 | A provider or alias test that cannot reach the endpoint reports `fake: ping` as its output. | `chat/service.py` `_probe` | V |
| D4 | An eval run never calls a model. It echoes the input, or refuses when the text looks like an attack. | `evals/runner.py:30,127` | V |
| D5 | Every tool server of kind `sql` is pointed at an in-memory demo warehouse, and an `openapi` server without a base URL at the demo pet store. | `tools/registry.py:468-473` | V |
| D6 | Memory always embeds with `fake-embed` hash vectors, and tool search always ranks with hash vectors, so both rankings carry no meaning. | `memory/book.py:926-929`, `tools/logic.py:148` | V memory, R tool search |
| D7 | Keyword turns (`maybe_compose`, `maybe_tools`), canned child answers, a model-free knowledge answer and a scripted agent draft sit in the turn. The first two are gated to dev and CI; the rest are not. | `skills/turn.py`, `tools/chat_loop.py`, `skills/delegate.py:149`, `knowledge/answer.py`, `agents/assist.py:37` | R |

The stand-in server already speaks the OpenAI protocol, with tool calls, streaming, embeddings and rerank. It
can be registered as an ordinary provider, which is what [M38a](../../09-plan/M38a-one-model-path.md) does.

## What already holds

- Native tool calling, with the error returned to the model so that it can correct the call.
- One choke point with entitlement, rate limit, quota, argument hash and manifest-drift checks.
- Approvals bound to the argument hash, single use, with segregation of duties.
- Untrusted wrapping, redaction and injection flagging on results. Secrets are scrubbed from stored arguments.
- Budgets that subagents inherit, with depth, cycle and fan-out limits.
- Scripted demo paths that run only in dev and CI, with a test.

## Direction

A strong agent does not come from a tool for each file format. It comes from a few sharp primitives, a real
computer, results passed by reference, long loops, and skills that teach the model how to use the computer for
a job. The owner chose that direction on 5 Nov 2026 ([OQ-90](../../open-questions.md),
[OQ-91](../../open-questions.md)): fix the framework first, add capability as primitives, a computer and
skills, and run code and the browser in a container for each conversation.

| Milestone | Outcome |
|---|---|
| [M38](../../09-plan/M38-tool-framework.md) | A1 to A12 and A14 are fixed. The schema's default limits apply. |
| [M38a](../../09-plan/M38a-one-model-path.md) | Product code has one model path and no fake model, scripted turn or demo fixture. |
| [M39](../../09-plan/M39-tool-surface.md) | Every tool has described parameters, with a lint. One workspace, with edit and search. Tools load on demand above a threshold. The model chooses skills. A15. |
| [M40](../../09-plan/M40-computer.md) | A container for each conversation, with the libraries spec 12 lists, and a Chromium browser driven through Playwright. |
| [M41](../../09-plan/M41-documents-media.md) | Skills for PDF, DOCX, PPTX and XLSX that drive the computer. Image generation and transcription through models the tenant registers. |
| [M42](../../09-plan/M42-measurement-trust.md) | Gym tasks that need chains, scored live for each model. Chat shows what a tool is doing. |

A13 stays with the owner as decision D4 of the
[November review](../review-2026-11-05/review-and-remediation-plan.md). M38 puts the call behind one function
so that either answer is a change in one place.
