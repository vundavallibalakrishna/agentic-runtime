# ADR-0003: Temporal for durable agent runs and background work

- Status: Accepted
- Date: 2026-10-20

## Context

Agent runs last seconds to hours, wait for human approvals and elicitations, call flaky tools and models, spawn subagents, and must survive deploys and crashes. Routines, ingestion, retention and deliveries also need schedules, retries and visibility.

## Decision

Use **Temporal** (self-hosted, Python SDK). One workflow per run (`AgentRunWorkflow`, id `run-{run_id}`); subagents as child workflows; all I/O in idempotent activities; signals for cancel/approval/input; Temporal Schedules for routines, syncs, rollups and sweeps. Workflow history carries only ids and counters, never prompts or tool payloads.

## Consequences

Exactly-once orchestration semantics with at-least-once activities (made idempotent by natural keys); human waits cost nothing; full execution history for debugging. Cost: Temporal cluster to operate (Helm chart + Postgres persistence), determinism discipline (replay tests in CI).

## Alternatives considered

Celery/RQ + DB state machine (rejected: hand-rolled timers, retries and resumption); Kafka-based orchestration (rejected: no durable timers/waits); LangGraph checkpoints (rejected: ties the runtime to a framework and still needs a job system).
