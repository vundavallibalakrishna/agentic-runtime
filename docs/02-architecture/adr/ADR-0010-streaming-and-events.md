# ADR-0010: Valkey streams for run events, transactional outbox for domain events; no Kafka in v1

- Status: Accepted
- Date: 2026-10-20

## Context

Clients need low-latency token streaming with resume; other components need reliable domain events (webhooks, notifications, cache invalidation).

## Decision

Run events go to Valkey Streams (`ar:run:{run_id}:events`, live, with resume by seq) and durable non-delta copies to `run_events`. Domain events use a Postgres outbox (`outbox_events`) relayed by `OutboxRelayWorkflow` to in-process subscribers ([domain-events](../../05-contracts/domain-events.md)).

## Consequences

No broker to operate; outbox gives atomicity with business changes. Cost: relay throughput ceiling (~2k events/s) — sufficient for v1; Kafka can be added behind the subscriber interface later.

## Alternatives considered

Kafka/Redpanda (rejected for v1: operational weight for single-tenant installs); Postgres LISTEN/NOTIFY only (rejected: no replay).
