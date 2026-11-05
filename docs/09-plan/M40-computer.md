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

**Do:** an image result (a screenshot, a rendered page, a chart) is sent to a model that has the vision
capability. A model without it gets the description from the vision alias.
