# ADR-0006: MCP (2026-07-28) as the only tool protocol; single gateway

- Status: Accepted
- Date: 2026-10-20

## Context

Tools come from many teams and vendors; we need discovery, schemas, annotations, progress, long-running tasks and elicitation in a standard way, plus a single enforcement point.

## Decision

All tools are MCP tools. Remote servers use Streamable HTTP (stateless 2026-07-28 revision; 2025-11-25 servers in compatibility mode). OpenAPI and SQL sources are wrapped by platform connector runtimes (`mcp-openapi`, `mcp-sql`). Built-ins are in-process MCP-shaped servers in `mcp-gateway`. `mcp-gateway` is the only MCP client: entitlement, validation, policy, approvals, credentials, result hygiene and audit happen there ([spec 08](../../03-specs/08-tool-registry-mcp.md)).

## Consequences

One code path for every tool call; vendor tools plug in directly. Cost: MCP spec evolution must be tracked (protocol version negotiation, conformance tests).

## Alternatives considered

Custom tool HTTP contract (rejected: reinvents MCP); letting the runtime call servers directly (rejected: no single choke point).
