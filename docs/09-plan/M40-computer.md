# M40 — A real computer

Goal: code, shell and a browser run in a container for each conversation ([OQ-91](../open-questions.md)).
Source: [the tool review](../testing/tools-review-2026-11-05/tools-review.md), section B.

Depends on: M39. Spec: [12-sandbox-manager](../03-specs/12-sandbox-manager.md). This milestone replaces the
in-process browser of M37 ([OQ-87](../open-questions.md)). Tasks are split into full task entries when the
milestone starts.

## M40-T01 The sandbox manager is on the call path

**Do:** the Docker driver starts a container for a conversation in development and CI. `sandbox-agent`
runs commands and file operations inside it. The host-subprocess fallback is refused outside dev.

## M40-T02 The computer image

**Do:** the image carries the Python set that spec 12 lists (pandas, numpy, polars, matplotlib, openpyxl,
python-docx, python-pptx, reportlab), a PDF library, LibreOffice, poppler, tesseract with configurable
languages, and ffmpeg. CI builds it.

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
