# M6 — Files, sandboxes & browser

Goal: agents get a computer. Each conversation (or routine/run scope) can own an isolated sandbox (gVisor/Kata pod in production, Docker in dev) where the agent runs Python/bash/node, installs allowlisted packages through the egress proxy, browses with a headless browser, and exports files as artifacts.

Exit criteria: "Analyse the attached CSV and chart revenue by month" produces a PNG artifact shown in the artifacts panel; `pip install requests` works only when the template allows packages; `curl https://example.org` from the sandbox fails unless allowlisted; browsing an allowlisted site returns snapshots and screenshots; idle sandboxes suspend and resume with their workspace intact.

---

### M6-T01 · Revision 0013 `sandboxes`, templates API
- **Depends on:** M5-T03, M2-T07
- **Areas:** `ar_domain/sandboxes/**`, migration 0013, `ar_api/routers/{sandbox_templates.py,sandboxes.py}`, seed of platform templates
- **Spec:** [spec 12 §2, §6](../03-specs/12-sandbox-manager.md#6-public-api-served-by-api), [schema §10](../04-data/schema.md#10-sandboxes-ar_domainsandboxes)
- **Do:** Tables of schema §10 (`sandbox_templates.allow_packages`); `GET/POST /api/v1/sandbox-templates`, `PATCH/DELETE /api/v1/sandbox-templates/{template_id}`; `GET /api/v1/sandboxes`, `GET /api/v1/sandboxes/{sandbox_id}`, `POST /api/v1/sandboxes/{sandbox_id}:terminate`, `GET /api/v1/conversations/{conversation_id}/sandbox`; platform templates `python-data` (default) and `browser`; resolver `sandbox_template` for agent validation; plan limit checks for CPU/memory.
- **Done when:** templates exceeding plan limits are rejected (422).
- **Tests:** integration per endpoint; resolver tests.

### M6-T02 · `sandbox-agent` and image `ar-sandbox`
- **Depends on:** M0-T11
- **Areas:** `services/sandbox_agent/**`, `images/sandbox/Dockerfile`
- **Spec:** [spec 12 §7, §7.1](../03-specs/12-sandbox-manager.md#7-sandbox-agent-tools), [internal-apis §5](../05-contracts/internal-apis.md#5-sandbox-agent-inside-the-sandbox-httpsandbox-ip8080)
- **Do:** Stateless MCP server at `POST /mcp` with `sandbox.exec` (streamed progress notifications of stdout/stderr, timeout, kill process group), `sandbox.read_file`, `sandbox.write_file`, `sandbox.list_files`; path confinement; new-file detection under `/workspace/outputs/`; admin endpoints (`/admin/claim`, `/admin/snapshot`, `/admin/restore`, health); bearer token check; image with the package set of §7.1, non-root, no package manager credentials.
- **Done when:** path traversal and symlink escapes are rejected; exec output is streamed and truncated per limits.
- **Tests:** unit tests (confinement, truncation); container test executing Python and producing an output file.

### M6-T03 · `sandbox-manager` with docker driver
- **Depends on:** M6-T01, M6-T02
- **Areas:** `services/sandbox_manager/src/ar_sandbox_manager/{routes.py,service.py,drivers/{base.py,docker.py},tokens.py}`
- **Spec:** [spec 12 §2–4.2](../03-specs/12-sandbox-manager.md#2-sandbox-lifecycle), [internal-apis §4](../05-contracts/internal-apis.md#4-sandbox-manager-base-httpsandbox-manager8003)
- **Do:** Internal endpoints of internal-apis §4 (`sandboxes:ensure`, get, suspend, resume, destroy, files list/read, `files:export`); lifecycle state machine; ensure lock semantics; per-sandbox token; Docker driver (`AR_SANDBOX_DRIVER=docker`, network attached only to the proxy network); per-tenant cap `AR_SANDBOX_MAX_PER_TENANT` and plan `max_concurrent_sandboxes`.
- **Done when:** concurrent `ensure` for the same scope returns one sandbox; suspend/resume preserves `/workspace`.
- **Tests:** integration with Docker (CI runner with Docker), concurrency test, cap test.

### M6-T04 · Kubernetes driver, warm pools, snapshots
- **Depends on:** M6-T03
- **Areas:** `ar_sandbox_manager/drivers/kubernetes.py`, `ar_sandbox_manager/warm_pool.py`, `deploy/helm/agentic-runtime/templates/sandboxes/*`
- **Spec:** [spec 12 §4.1](../03-specs/12-sandbox-manager.md#41-kubernetes-production), [helm-k8s](../07-ops/helm-k8s.md), [ADR-0013](../02-architecture/adr/ADR-0013-sandbox-isolation.md)
- **Do:** Pods with `runtimeClassName` (`AR_SANDBOX_DEFAULT_RUNTIME_CLASS`, gVisor default, Kata per template), PVC or ephemeral workspace per template, default-deny NetworkPolicy allowing only Squid and DNS, no service account token, seccomp/AppArmor, resource limits; warm pools per template (`AR_SANDBOX_WARM_POOL`); snapshots (tar of `/workspace` to `files(kind='sandbox_snapshot')`) on suspend and every `AR_SANDBOX_SNAPSHOT_INTERVAL_S`; restore on resume.
- **Done when:** on a kind cluster with gVisor, sandboxes start from warm pool in < 2 s p95 and cannot reach other pods.
- **Tests:** e2e on kind (nightly job): network isolation (connect to `api` service fails), warm-pool claim latency, snapshot/restore.

### M6-T05 · Egress proxy and allowlists
- **Depends on:** M6-T03
- **Areas:** `images/squid/{Dockerfile,squid.conf,ar-egress-helper.py}`, `ar_sandbox_manager/egress.py`
- **Spec:** [spec 12 §5](../03-specs/12-sandbox-manager.md#5-egress-control), [threat-model T7–T8](../06-security/threat-model.md)
- **Do:** Squid with external ACL helper calling `GET /internal/v1/egress/check` (sandbox identity via proxy auth token); allowed hosts = (template ∪ agent extra) ∩ tenant allowlist, plus `AR_SANDBOX_PACKAGE_MIRRORS` when `allow_packages`; deny private CIDRs `AR_EGRESS_DENY_CIDRS`; CONNECT only to 443; access logs with sandbox id to Loki.
- **Done when:** disallowed hosts get 403 from the proxy; DNS rebinding to a private IP is blocked.
- **Tests:** integration (compose: sandbox → squid → stub hosts); unit tests for allowlist computation.

### M6-T06 · Gateway sandbox routing, artifacts and reaper
- **Depends on:** M6-T03, M4-T05
- **Areas:** `ar_mcp_gateway/builtins/{sandbox.py,files.py}`, `ar_system/workflows/sandbox_reaper.py`
- **Spec:** [spec 08 §9](../03-specs/08-tool-registry-mcp.md#9-built-in-tool-schemas-platform-servers-executed-in-process-by-mcp-gateway-unless-noted), [spec 12](../03-specs/12-sandbox-manager.md), [spec 13 §6](../03-specs/13-files-artifacts.md#6-artifacts)
- **Do:** `sandbox.*` forwarding (ensure by `sandbox_scope_key`, progress → `tool_call.progress` events), `sandbox.export_file` and auto-export of new `/workspace/outputs/` files → `artifact.created`; `files.attach_to_sandbox`; `SandboxReaperWorkflow` (idle suspend, max lifetime destroy, orphan pod cleanup); usage metrics `sandbox_cpu_seconds`, `sandbox_sessions`.
- **Done when:** the M6 exit CSV-chart scenario passes with fake-llm scripted code.
- **Tests:** integration end-to-end (docker driver); Temporal reaper test.

### M6-T07 · Browser tools
- **Depends on:** M6-T06
- **Areas:** `ar_sandbox_agent/browser/**`, `images/sandbox/Dockerfile` (Playwright Chromium)
- **Spec:** [spec 12 §7](../03-specs/12-sandbox-manager.md#7-sandbox-agent-tools), [prompt-injection §6](../06-security/prompt-injection.md#6-exfiltration-via-images-links-and-tools)
- **Do:** `browser.navigate`, `browser.snapshot` (accessibility tree with refs), `browser.click`, `browser.type`, `browser.press`, `browser.scroll`, `browser.screenshot` (stored as artifact, `browser.screenshot` event), `browser.submit_form` (W2); egress via proxy; results marked untrusted.
- **Done when:** navigation to a local test site produces stable refs; submit_form requires approval by default.
- **Tests:** container tests against a static test site; policy default test for `browser.submit_form`.

### M6-T08 · Files completion: previews and artifact APIs
- **Depends on:** M6-T06
- **Areas:** `ar_ingest/workflows/file_process.py`, `ar_api/routers/{files.py,sandboxes.py}`
- **Spec:** [spec 13](../03-specs/13-files-artifacts.md), [spec 12 §6](../03-specs/12-sandbox-manager.md#6-public-api-served-by-api)
- **Do:** Text extraction cache for `files.read` (PDF/Office via Docling light mode), CSV/XLSX previews (first 1,000 rows), `GET /api/v1/sandboxes/{sandbox_id}/files`, `GET /api/v1/sandboxes/{sandbox_id}/files/content`, `POST /api/v1/sandboxes/{sandbox_id}/files:export`; `AR_FILES_PROXY_DOWNLOADS` mode; content-disposition and CSP for downloads (HTML served as attachment/text only).
- **Done when:** HTML artifacts can never render inline in the app origin.
- **Tests:** integration; security test for HTML/SVG download headers.

### M6-T09 · Web: artifacts and computer panels, sandbox admin
- **Depends on:** M6-T07, M6-T08
- **Areas:** `apps/web/src/components/chat/{ArtifactsPanel,ComputerPanel,FileViewer}/**`, `apps/web/src/app/(admin)/admin/sandboxes/**`
- **Spec:** [spec 19](../03-specs/19-web-app.md)
- **Do:** Artifacts panel (list, viewers for images, PDF, CSV/XLSX table, Markdown, code, charts), computer panel (live exec output from `tool_call.progress`, browser screenshots timeline, workspace file tree), sandbox admin (templates CRUD, live sandboxes with terminate).
- **Done when:** M6 exit scenario is demonstrable in the UI.
- **Tests:** Vitest viewers; Playwright CSV-chart scenario; axe.
