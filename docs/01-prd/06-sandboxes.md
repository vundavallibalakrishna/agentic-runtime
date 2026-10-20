# PRD 06 — Sandboxes & browser

Agents run code and drive a headless browser inside isolated, network-restricted sandboxes, producing files the user can download. Spec: [spec 12](../03-specs/12-sandbox-manager.md), [spec 13](../03-specs/13-files-artifacts.md), threats T7/T8 in [threat-model](../06-security/threat-model.md). Plan: [M6](../09-plan/M06-sandboxes.md).

### US-SBX-01 · Run code to analyse data (P0)
As a **member**, I want the agent to run Python or shell code on my uploaded files so that I get real analysis, not guesses.
- With `sandbox.enabled`, the agent uses `sandbox.exec`, `sandbox.write_file`, `sandbox.read_file`, `sandbox.list_files`; `files.attach_to_sandbox` copies my files to `/workspace/inputs/`.
- Output streams to the UI (`sandbox.output`), the sandbox status is visible (`sandbox.status`); each exec respects the template's timeout.
- Spec: spec 12 §7. Plan: M6-T02, M6-T03, M6-T06.

### US-SBX-02 · Get files back as artifacts (P0)
As a **member**, I want charts, spreadsheets and documents created by the agent to appear in the chat for download.
- `sandbox.export_file` stores the file as an artifact (`files.kind='artifact'`), emits `artifact.created`, and the UI shows a preview (images, PDF, CSV/XLSX table, Markdown, code) and download.
- Spec: spec 12 §7, spec 13. Plan: M6-T06, M6-T08, M6-T09.

### US-SBX-03 · Isolation guarantees (P0)
As a **security officer**, I want sandboxes that cannot reach internal systems or other tenants.
- Pods run with gVisor (or Kata per template), non-root, no service-account token, default-deny network except the egress proxy and DNS; cloud metadata, cluster and private ranges are always denied.
- Escape and egress tests in the security suite pass ([testing-strategy §7](../08-quality/testing-strategy.md#7-security-tests)).
- Spec: spec 12 §4–5. Plan: M6-T04, M6-T05, M14-T07.

### US-SBX-04 · Controlled internet and package access (P0)
As a **tenant admin**, I want to control which hosts sandboxes can reach.
- Allowed hosts = (template allowlist ∪ agent `extra_egress_allowlist`) ∩ tenant allowlist, plus configured package mirrors; denied requests are logged (`ar_sandbox_egress_denied_total`, audit `sandbox.egress_denied`) and the agent receives a clear error.
- Spec: spec 12 §5. Plan: M6-T05.

### US-SBX-05 · Persistent workspace per conversation (P0)
As a **member**, I want my files and installed packages to still be there when I come back to the conversation.
- Default scope `conv:{conversation_id}`; idle sandboxes suspend with a workspace snapshot and resume on the next use; terminated at max lifetime or when the conversation is deleted; I can browse the workspace (`GET /api/v1/sandboxes/{sandbox_id}/files`) and export files.
- Spec: spec 12 §2, §6. Plan: M6-T04, M6-T09.

### US-SBX-06 · Browse the web for me (P1)
As a **member**, I want the agent to read web pages and fill simple forms with a real browser.
- `browser.*` tools (navigate, snapshot, click, type, press, scroll, screenshot); screenshots appear live (`browser.screenshot`); `browser.submit_form` is `W2` and needs approval by default; egress rules apply.
- Spec: spec 12 §7. Plan: M6-T07.

### US-SBX-07 · Administer sandbox templates and usage (P0)
As a **tenant admin**, I want to manage templates (image, resources, timeouts, allowlists, runtime class) and see/terminate running sandboxes.
- `GET/POST/PATCH/DELETE /api/v1/sandbox-templates` (platform templates read-only), `GET /api/v1/sandboxes`, `:terminate`; per-tenant concurrency limited by plan (`max_concurrent_sandboxes`) and `AR_SANDBOX_MAX_PER_TENANT`; CPU seconds metered as usage.
- Spec: spec 12 §6, [spec 17](../03-specs/17-audit-usage-metering.md). Plan: M6-T01, M6-T09.
