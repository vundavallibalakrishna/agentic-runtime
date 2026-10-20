# Spec 12: Sandboxes, computer and browser (`sandbox-manager`, `sandbox-agent`)

Deployables: `sandbox-manager` (`services/sandbox_manager`, package `ar_sandbox_manager`, port 8003) manages sandbox lifecycle via a driver (`docker` for local dev, `kubernetes` for prod); `sandbox-agent` (`services/sandbox_agent`, package `ar_sandbox_agent`, port 8080, baked into image `ar-sandbox`) runs inside every sandbox and exposes the `sandbox.*` and `browser.*` MCP tools. Template/sandbox endpoints are served by `api`. Owns `sandbox_templates`, `sandboxes` ([schema §10](../04-data/schema.md#10-sandboxes-ar_domainsandboxes)). Decision: [ADR-0013](../02-architecture/adr/ADR-0013-sandbox-isolation.md). Security: [threat-model T7/T8](../06-security/threat-model.md). PRD: [06-sandboxes](../01-prd/06-sandboxes.md).

## 1. Responsibilities

1. Provide each agent a persistent, isolated Linux "computer" per scope (`conversation`, `agent_user`, `agent`) with a workspace, code execution, file I/O and a headless browser.
2. Lifecycle: ensure (create/resume), touch, idle suspend (snapshot workspace to S3), resume, terminate, reap; warm pools.
3. Isolation: gVisor (default) or Kata runtime class, non-root, read-only root FS, no service-account token, NetworkPolicy, egress only via the Squid proxy with per-sandbox allowlists, resource limits.
4. Meter CPU seconds and sessions; enforce quotas.
5. Proxy workspace file listing/download to the web UI computer panel (via `api`) and export files as artifacts.

## 2. Sandbox lifecycle

```mermaid
stateDiagram-v2
  [*] --> pending: ensure (no live sandbox for scope_key)
  pending --> starting: driver create
  starting --> ready: sandbox-agent /healthz ok
  starting --> failed
  ready --> suspending: idle > idle_suspend_s or explicit
  suspending --> suspended: snapshot uploaded, compute stopped
  suspended --> resuming: ensure
  resuming --> ready: snapshot restored
  ready --> terminating: max_lifetime / conversation deleted / admin
  suspended --> terminating: retention / admin
  terminating --> terminated
```

`scope_key`: `conv:{conversation_id}` | `au:{agent_id}:{user_id}` | `agent:{agent_id}`. One live sandbox per (`tenant_id`, `scope_key`) (unique partial index). `agent` scope sandboxes are shared by all users of the agent and therefore restricted to templates with `max_classification ≤ internal` and are not allowed for agents bound to `R1+` user-data tools (publish-time validation).

## 3. Internal API (`sandbox-manager`)

As listed in [internal-apis §4](../05-contracts/internal-apis.md#4-sandbox-manager-base-httpsandbox-manager8003), plus:

| Method | Path | Caller | Purpose |
|---|---|---|---|
| GET | `/internal/v1/egress/check?sandbox_id=&host=&token=` | `squid` external ACL helper | `200 OK` if the host is allowed for that sandbox, else `403`; cached by Squid 60 s |
| POST | `/internal/v1/sandboxes/{sandbox_id}/files:export` | `mcp-gateway`, `api` | `{path, name?, run_id?, conversation_id?}` → reads the workspace file, stores it in S3 as `files(kind='artifact')`, returns `{file_id}` |

`ensure` semantics: lock `ar:sbx:lock:{tenant}:{scope_key}` (Valkey, 60 s); find live row; `ready` → touch and return; `suspended` → resume; none → create from warm pool or cold. Blocks ≤ 30 s (`AR_SANDBOX_ENSURE_TIMEOUT_S`); returns `{sandbox_id, status, endpoint_url, token}` where `token` is a per-sandbox bearer (32 random bytes, only its sha256 stored) delivered to the sandbox at claim time and to `mcp-gateway` (cached in Valkey encrypted with `AR_TOKEN_CACHE_KEY`, TTL = sandbox lifetime).

## 4. Drivers

### 4.1 `kubernetes` (production)
- Namespace `ar-sandboxes` (shared tier) or `ar-sbx-{tenant_slug}` (dedicated tiers). One Pod per sandbox, name `sbx-{sandbox_id_short}`, labels `ar/tenant`, `ar/sandbox`, `ar/template`.
- Pod spec: `runtimeClassName: gvisor|kata`; `automountServiceAccountToken: false`; container `ar-sandbox@sha256:…` user `10001`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`; volumes: `/workspace` emptyDir (`sizeLimit = disk_gb`), `/tmp` emptyDir 1 GiB, `/home/sandbox` emptyDir; resources `requests = limits = {cpu_millis, memory_mb}`; `activeDeadlineSeconds = max_lifetime_s`; env `HTTP_PROXY/HTTPS_PROXY=http://sbx-{id}:{token}@squid.ar-system:3128`, `NO_PROXY=` (none); `hostNetwork/hostPID/hostIPC: false`; DNS policy `None` with resolver = cluster DNS only for the proxy.
- NetworkPolicy `ar-sandbox-default`: ingress only from pods labelled `app.kubernetes.io/name in (mcp-gateway, sandbox-manager)` on 8080; egress only to Squid (3128) and kube-dns (53).
- Snapshot: on suspend the manager calls sandbox-agent `POST /admin/snapshot` which streams a `tar.zst` of `/workspace` to the manager, which uploads it to S3 (`files.kind='sandbox_snapshot'`); then deletes the pod. Resume: new pod, then `PUT /admin/restore` with the archive.
- Warm pool: per platform template `AR_SANDBOX_WARM_POOL` (default `default=4,browser=2`) unclaimed pods in `ar-sandboxes-warm` with no network egress until claimed; claim = `POST /admin/claim {sandbox_id, token, tenant_id, egress_identity}` with a bootstrap token from a Secret, then relabel. Warm pods are recycled after 1 h.
- Falco rules (deployed via Helm) alert on shell spawns of unexpected binaries in sandbox namespaces only as defence in depth.

### 4.2 `docker` (local dev, CI)
`aiodocker`; one container per sandbox on network `ar-sandbox-net` (internal, no internet) with Squid attached to both networks; runtime `runc` (`runtime_class='runc_dev'`) unless `runsc` is installed (`AR_SANDBOX_DOCKER_RUNTIME=runsc`). Snapshots identical (via the agent). Forbidden when `AR_ENV=prod` (startup check).

## 5. Egress control

- Squid 7.7 (`images/squid/`) with `external_acl_type ar_egress ttl=60 %LOGIN %DST /usr/local/bin/ar-egress-helper` calling `/internal/v1/egress/check`; CONNECT allowed only to port 443; no SSL bump (TLS end-to-end); access log to stdout (shipped to Loki) with sandbox id.
- Allowed hosts for a sandbox = (template `egress_allowlist` ∪ agent `sandbox.extra_egress_allowlist`) ∩ tenant `settings.egress_allowlist` (when the tenant list is non-empty); plus platform package mirrors from `AR_SANDBOX_PACKAGE_MIRRORS` (e.g. internal PyPI/npm proxies) when the template has `allow_packages: true` in its config. `*` is rejected in prod.
- Cloud metadata IPs, cluster CIDRs and RFC1918 ranges are always denied (`AR_EGRESS_DENY_CIDRS`), checked after DNS resolution by Squid ACLs.

## 6. Public API (served by `api`)

Permissions: `sandboxes:manage` for templates and admin views; end users access their conversation's sandbox through conversation visibility.

#### GET /api/v1/sandbox-templates
Tenant + platform templates. Item `SandboxTemplate {id, scope, slug, name, image_ref, runtime_class, cpu_millis, memory_mb, disk_gb, allow_browser, egress_allowlist, max_classification, idle_suspend_s, max_lifetime_s, exec_timeout_s, retention_days, status}`.

#### POST /api/v1/sandbox-templates
Body as above (minus id/scope). `image_ref` must be digest-pinned and from an allowed registry (`AR_SANDBOX_ALLOWED_REGISTRIES`); limits ≤ plan (`max_sandbox_cpu_millis`, `max_sandbox_memory_mb`).

#### PATCH /api/v1/sandbox-templates/{template_id}
#### DELETE /api/v1/sandbox-templates/{template_id}
409 if referenced by agent definitions (bindings `sandbox_template`).

#### GET /api/v1/sandboxes
`sandboxes:manage`. Query `status`, `agent_id`, `user_id`, `template_id`. Item `Sandbox {id, template: {id, slug}, scope, conversation_id, agent_id, user_id, status, cpu_seconds, last_active_at, started_at}`.

#### GET /api/v1/sandboxes/{sandbox_id}
Admins, or the user owning the conversation/scope.

#### POST /api/v1/sandboxes/{sandbox_id}:terminate
Admins or owner. Audit `sandbox.terminated`.

#### GET /api/v1/conversations/{conversation_id}/sandbox
Conversation viewers. `{sandbox: Sandbox|null}` (the conversation-scope sandbox or the agent_user sandbox used by its runs).

#### GET /api/v1/sandboxes/{sandbox_id}/files
Query `path` (default `/workspace`), `recursive=false`. Items `{path, name, type: file|dir, size_bytes, modified_at}`. Proxied to the manager. Suspended sandboxes are listed from the snapshot manifest (stored as `files.preview.manifest`) without resuming.

#### GET /api/v1/sandboxes/{sandbox_id}/files/content
Query `path`. Streams the file (≤ 100 MiB) with `Content-Disposition: attachment`; HTML/SVG always served as `application/octet-stream` (no inline rendering, XSS defence).

#### POST /api/v1/sandboxes/{sandbox_id}/files:export
Body `{path, name?}` → `{file: File}` (artifact owned by the caller, attached to the conversation).

## 7. Sandbox-agent tools

Exposed by `sandbox-agent` at `POST /mcp` (MCP 2026-07-28, stateless) to `mcp-gateway` only. Every result carries `_meta["io.agentic-runtime/usage"] = {cpu_seconds_total}` (cgroup v2 `cpu.stat` cumulative) from which the gateway meters deltas.

| Tool | Input | Output |
|---|---|---|
| `sandbox.exec` | `{command: string (bash -lc), cwd?: "/workspace", timeout_s?: 1..exec_timeout_s, stdin?: string ≤ 1 MiB, env?: {k: v} (no secrets; keys `^[A-Z_][A-Z0-9_]*$`)}` | `{exit_code, stdout (last 16 KiB), stderr (last 8 KiB), truncated: bool, duration_ms, new_files: [path] (under /workspace, created/modified)}`; stdout/stderr streamed as MCP progress → `sandbox.output` events. Timeout kills the process group (exit 124). |
| `sandbox.read_file` | `{path, offset?: 0, limit?: ≤ 65536, encoding?: "utf8"\|"base64"}` | `{content, size_bytes, eof}` |
| `sandbox.write_file` | `{path, content, encoding?: "utf8"\|"base64", append?: false}` (≤ 10 MiB) | `{bytes_written}` |
| `sandbox.list_files` | `{path?: "/workspace", recursive?: false, max_entries?: ≤ 1000}` | entries |
| `sandbox.export_file` | `{path, name?}` | Implemented by `mcp-gateway` (not the agent): calls manager `files:export`, emits `artifact.created`, returns `{file_id, name}` |
| `browser.navigate` | `{url}` | `{url, title, status}` (egress rules apply) |
| `browser.snapshot` | `{max_chars?: ≤ 40000}` | Accessibility-tree text with element refs `[ref=e12]` (untrusted content) |
| `browser.click` | `{ref}` | new snapshot excerpt |
| `browser.type` | `{ref, text, submit?: false}` | excerpt (W1) |
| `browser.press` | `{key}` | excerpt |
| `browser.scroll` | `{direction: up\|down, amount?: 1..10 (viewports)}` | excerpt |
| `browser.screenshot` | `{full_page?: false}` | PNG → gateway stores `files(kind='artifact')` and emits `browser.screenshot` |
| `browser.submit_form` | `{ref}` | Submits a form (W2: approval by default) |

Paths are confined to `/workspace` and `/tmp` (realpath check; symlinks escaping are rejected). Files under `/workspace/outputs/` that are new or modified after `sandbox.exec` are exported automatically as artifacts (≤ 20 files, ≤ 100 MiB each per call).

Admin endpoints on the agent (manager only, bootstrap/sandbox token): `POST /admin/claim`, `POST /admin/snapshot`, `PUT /admin/restore`, `GET /healthz`, `GET /files`, `GET /files/content`, `PUT /files/content`.

### 7.1 Image `ar-sandbox` (`images/sandbox/Dockerfile`)
Debian 13 slim; Python 3.14 with `uv`, `pandas`, `numpy`, `polars`, `matplotlib`, `seaborn`, `scipy`, `openpyxl`, `python-docx`, `python-pptx`, `reportlab`, `pypdf`, `duckdb`; Node 24 with `pnpm`; Chromium + Playwright 1.64 (template `browser`); LibreOffice headless (template `data-science`); `git`, `curl`, `jq`, `ripgrep`, fonts (Noto incl. Indic scripts); user `sandbox` (10001). Image is signed (cosign) and scanned in CI; templates reference digests.

## 8. Configuration (`sandbox-manager`)

| Variable | Default | Purpose |
|---|---|---|
| `AR_SANDBOX_DRIVER` | `docker` (dev) / `kubernetes` | |
| `AR_SANDBOX_NAMESPACE` | `ar-sandboxes` | |
| `AR_SANDBOX_DEFAULT_RUNTIME_CLASS` | `gvisor` | |
| `AR_SANDBOX_DOCKER_RUNTIME` | `runc` | `runsc` if installed |
| `AR_SANDBOX_ENSURE_TIMEOUT_S` | `30` | |
| `AR_SANDBOX_WARM_POOL` | `default=4,browser=2` | |
| `AR_SANDBOX_ALLOWED_REGISTRIES` | `registry.local/ar` | |
| `AR_SANDBOX_PACKAGE_MIRRORS` | empty | |
| `AR_EGRESS_DENY_CIDRS` | metadata + RFC1918 + cluster | |
| `AR_SANDBOX_MAX_PER_TENANT` | plan `max_concurrent_sandboxes` (default 50) | |

## 9. Failure modes

| Failure | Behaviour |
|---|---|
| Node pressure / pod evicted | Status `failed`; next `ensure` creates a new sandbox restoring the last snapshot (work since the last snapshot is lost; snapshots also taken every 10 min of activity, `AR_SANDBOX_SNAPSHOT_INTERVAL_S=600`). |
| Ensure timeout | Tool error `sandbox_unavailable` (retriable); runtime surfaces to the model. |
| Quota exceeded (`sandbox_cpu_seconds` or concurrency) | Tool error `quota_exceeded`. |
| Squid helper cannot reach manager | Deny (fail closed). |

## 10. Metrics

`ar_sandboxes{status,template}`, `ar_sandbox_ensure_seconds{path=warm|cold|resume}`, `ar_sandbox_exec_seconds`, `ar_sandbox_cpu_seconds_total{tenant}`, `ar_sandbox_egress_denied_total{reason}`, `ar_sandbox_snapshot_bytes`, `ar_sandbox_warm_pool_available{template}`.

## 11. Test plan

- Unit: path confinement (traversal, symlink escape), egress allow computation, state machine.
- Integration (docker driver in CI): ensure → exec Python producing `/workspace/outputs/chart.png` → artifact created; suspend → resume preserves files; egress to non-allowlisted host blocked, allowlisted host allowed; metadata IP blocked; timeout kills process; browser navigate+snapshot against a local test site (`ar_testing.sites`).
- Kubernetes (nightly, kind cluster with gVisor): pod spec conformance (`kubectl get pod -o json` assertions), NetworkPolicy isolation (sandbox cannot reach `api`, Postgres, other sandboxes), warm pool claim.
- Security regression suite (`tests/security/sandbox_escape/*.sh`): known escape attempts must fail.
