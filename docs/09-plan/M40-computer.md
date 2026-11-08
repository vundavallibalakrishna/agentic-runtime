# M40 — A real computer

Goal: code, shell and a browser run in a container for each conversation ([OQ-91](../open-questions.md)).
Source: [the tool review](../testing/tools-review-2026-11-05/tools-review.md), section B.

Depends on: M39. Spec: [12-sandbox-manager](../03-specs/12-sandbox-manager.md). This milestone replaces the
in-process browser of M37 ([OQ-87](../open-questions.md)). Tasks are split into full task entries when the
milestone starts.

## M40-T01 The sandbox manager is on the call path

The spec's design (12 §6) runs code and file I/O inside the container through `sandbox-agent` over HTTP, with
the workspace in a volume, not a host bind-mount. So this is built in stages: **T01** makes the agent run
commands and file operations inside a sandbox; **T01b** builds the `ar-sandbox` image that bakes it (OQ-37);
**T01c** gives the manager an `aiodocker` driver that starts and claims a container; **T01d** proxies the
sandbox tools to the agent inside the container when the row carries an endpoint; **T01e** makes the
in-process path start that container — `ensure_scope` calls an injected launcher registered on the store, so
code, shell and files run inside a per-conversation container on a developer's machine ([OQ-119](../open-questions.md)).

**Do (T01e):**

- The aiodocker primitive moves to `ar_common.sandbox_docker` (with a synchronous, loop-safe
  `DockerSandboxLauncher`) so the api and runtime register it on the chat store without importing the manager;
  the manager's docker driver re-exports it.
- `ensure_scope` calls `store.sandbox_launcher` when the row's driver is `docker`, stamping
  `endpoint_url`/`container_id`/`agent_token`; `_terminate` stops the container. A start failure fails the
  sandbox (`SandboxStartError`) and is surfaced, not silently downgraded to the host.
- The api registers the launcher only when `AR_SANDBOX_IMAGE` names the local image and the install allows an
  unisolated sandbox (`AR_SANDBOX_ALLOW_UNISOLATED`); with no launcher the tools run on the dev host, as before.

**Done when (T01e):** with the image built and the two settings on, a chat's `general.shell`/`exec` and file
tools run inside a container, proven by a docker-gated integration test that starts a real container through
`ensure_scope` and runs a command in it. Suspend/resume of a container-backed workspace (via the agent's
snapshot endpoint) and registering the launcher in the Temporal runtime worker are follow-ups ([OQ-119](../open-questions.md)).

**Tests:** `libs/ar_domain/tests/unit/test_m40_sandbox_launcher.py`,
`libs/ar_domain/tests/integration/test_m40_container_launch.py`.

**Do (T01):**

- `sandbox-agent` runs `sandbox.exec` in its `/workspace`: a bash command with a confined `cwd`, a timeout
  that kills the process group (exit 124), `stdin` and `env`, returning `exit_code`, `stdout`/`stderr`
  (capped), `truncated`, `duration_ms` and the files the command created or changed.
- `sandbox.read_file` takes a byte range and an encoding; `sandbox.write_file` takes base64 and append and
  caps at 10 MiB; `sandbox.list_files` recurses within a cap. Every result carries the cumulative
  `cpu_seconds_total` the gateway meters deltas from.
- Paths stay inside the sandbox root; a `cwd` or path that escapes is refused.

**Done when (T01):** the agent runs a command, reports the files it wrote, times out a long one, and reads
and writes files by range and base64 — all confined to its workspace.

**Tests:** `services/sandbox_agent/tests/unit/test_m40_agent.py`.

## M40-T02 The computer image

**Do:**

- Bake the Python toolbox the spec lists into the `ar-sandbox` image so a command that runs `python3` finds
  it: pandas, numpy, polars, scipy, matplotlib, seaborn, openpyxl, python-docx, python-pptx, reportlab, pypdf,
  pdfplumber, duckdb, pillow, pytesseract. The set is pinned in `images/sandbox/sandbox-tools.txt`, compiled
  from `sandbox-tools.in` with `uv pip compile --universal` for Python 3.14, and installed into the agent venv.
- Add the document, OCR and media stack: LibreOffice headless (writer/calc/impress filters), poppler-utils,
  tesseract with configurable languages (`SANDBOX_TESSERACT_LANGS`, default `eng`), ffmpeg, and Noto fonts
  (incl. CJK and Indic scripts).
- CI's `images` job builds the image (no timeout; `scripts/build_images.sh`). Node, Chromium and Playwright
  stay for M40-T04.

**Done when:** the image builds in CI and a command run in a started container imports the toolbox
(`python3 -c "import pandas, matplotlib, docx, pptx, pdfplumber"`), converts a document with LibreOffice and
runs tesseract. Verified locally by building the full image and importing the toolbox inside it.

**Tests:** the CI `images` build is the gate; `libs/ar_domain/tests/integration/test_m40_container_launch.py`
covers a command running in a real container.

## M40-T03 Kubernetes and egress

**Do:** the Kubernetes driver with the gVisor runtime class, the egress proxy and allow list, and a kind
install that runs a command in a pod.

## M40-T04 A browser that runs pages

**Do:** Chromium through Playwright inside the computer. `navigate`, `snapshot` (an accessibility tree with
element refs), `click`, `type`, `press`, `select`, `hover`, `scroll`, `wait_for`. Each tool has its own
schema. Navigation off the allow list and form submission keep their approval rules.

## M40-T05 Files, tabs and screenshots

**Do:** upload from and download to the workspace, tabs, a real screenshot, save a page as PDF, and a stored
sign-in through a connection.

## M40-T06 The model sees images

Done before the container tasks because it needs no new infrastructure: it is domain code on the existing
agent loop, so a tenant that connects a vision model sees it work today, and the browser and sandbox of
T01–T05 feed it richer images later.

**Do:**

- The agent loop collects the images a tool batch produced — a result's `artifacts` and its chart
  `presentation` — into `build_image_message` after every tool call in the batch is answered (OpenAI
  requires that order). `tools/images.py` holds `collect_images` and `build_image_message`.
- When the agent's reasoning model has the `vision` capability, the images go to the model as `image_url`
  parts on a `user` message, so the model sees them. The same OpenAI-compatible endpoint and data-URI
  encoding that `documents.vision` already uses carry them.
- When the reasoning model cannot read images but the agent's vision alias can, that alias describes each
  image (through `ask_image`) and the description is appended instead.
- When no vision-capable model is connected, nothing is injected and the turn's messages are unchanged, so
  no existing behaviour moves until a tenant connects a vision model ([OQ-115](../open-questions.md)).
- At most four images per batch, each under 8 MiB, reach the model. The injected note and the description
  prompt both say the images are untrusted content (never-skip rule 5).

**Done when:** a turn whose tool drew a chart or took a screenshot shows that image to a vision-capable
reasoning model, a text-only model gets the description, and a tenant with no vision model runs exactly as
before.

**Tests:** `test_m40_model_sees_images.py` — `collect_images` reads artifacts and the chart presentation,
skips non-images and other tenants and caps the count; `build_image_message` shows a vision model the
picture, gets a description from the vision alias for a text-only model, and is silent with no vision model;
the loop injects a tool's image into the next model call and the run completes.
