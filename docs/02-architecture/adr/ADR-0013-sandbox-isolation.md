# ADR-0013: gVisor (default) / Kata sandboxes on Kubernetes; Docker driver for dev

- Status: Accepted
- Date: 2026-10-20

## Context

Agents execute arbitrary code and browse the web; a sandbox escape or data exfiltration would be critical.

## Decision

One pod per sandbox with `runtimeClassName: gvisor` (or `kata` for stronger isolation), hardened pod security, NetworkPolicy allowing only the Squid egress proxy with per-sandbox allowlists, no service-account token, snapshots to object storage for persistence ([spec 12](../../03-specs/12-sandbox-manager.md)). Docker driver only for dev/CI.

## Consequences

Strong isolation with acceptable start latency (warm pools). Cost: gVisor syscall overhead for heavy workloads (Kata template available).

## Alternatives considered

Plain containers (rejected: kernel attack surface); Firecracker microVMs managed by us (rejected: operational complexity; Kata covers the VM-isolation need).
