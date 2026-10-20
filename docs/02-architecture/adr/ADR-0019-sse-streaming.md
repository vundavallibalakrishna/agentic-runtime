# ADR-0019: Server-Sent Events for client streaming

- Status: Accepted
- Date: 2026-10-20

## Context

Browsers, Slack/Teams bridges and SDKs need token streaming and run events.

## Decision

SSE over HTTP/1.1 and HTTP/2 with `Last-Event-ID` resume; heartbeats every 15 s; one stream per run or per conversation ([stream-events](../../05-contracts/stream-events.md)).

## Consequences

Works through proxies and the BFF cookie model; trivial client code. Cost: unidirectional (client actions are normal POSTs).

## Alternatives considered

WebSockets (rejected: sticky sessions, more complex auth and proxying).
