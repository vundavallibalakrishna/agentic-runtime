# ADR-0004: Custom, thin agent loop instead of an agent framework

- Status: Accepted
- Date: 2026-10-20

## Context

The loop must integrate tightly with Temporal activities, policy/approvals, budgets, streaming events, tenant isolation and auditing. Agent frameworks evolve quickly and hide control flow.

## Decision

Implement the loop in `ar_runtime` (~1–2k lines): context assembly, model step, parallel tool batch, approvals/elicitation waits, compaction, delegation, finalisation ([spec 07](../../03-specs/07-agent-runtime.md)). Model access via OpenAI-compatible Chat Completions through `model-gateway`; tools via MCP through `mcp-gateway`.

## Consequences

Full control over durability, security checks and events; no framework lock-in; easy to test with `fake-llm`. Cost: we implement features frameworks offer (compaction, planning prompts) ourselves.

## Alternatives considered

LangGraph, CrewAI, other agent SDKs (rejected: duplicated state/persistence models conflicting with Temporal; harder to guarantee policy enforcement on every call).
