# ADR-0030: Production topology

- Status: Accepted
- Date: 2026-11-10

## Context

The API process currently runs the model loop, can fall back to a host shell, and serves chat from an in-memory store. More than one API replica then splits sessions, idempotency, and run events. Tool calls do not all go through the gateway. This record is the production shape. Stages 1, 6, and 8 implement it. It closes the open deferral in [OQ-93](../../open-questions.md).

## Decision

- The API is stateless. It does not run the model loop, a shell, or a browser.
- The runtime worker owns the loop. One Temporal activity is one step.
- The tool gateway is the only caller of tools, including built-ins. It applies policy, approvals, result wrapping, and secrets.
- The sandbox manager is the only creator of pods. Production pods are Kubernetes. An empty endpoint means the tool does not run.
- Postgres, with row-level security and pgvector, is the read model ([ADR-0033](ADR-0033-postgres-read-model.md)).
- The object store holds original bytes.
- Valkey holds sessions, idempotency, and rate limits.
- An event bus feeds server-sent events on every API replica.
- Host bash is a development driver only. It is absent from production images.
- Packs are out of process, with a signed manifest and their own schema. Core never imports a pack ([ADR-0034](ADR-0034-signed-pack-model.md)).

## Consequences

A replica can start or stop without moving a conversation. A tool cannot run on the API host. A missing sandbox endpoint is a refusal (`sandbox_unavailable` in Stage 1), not a host command. Secrets stay in the gateway and never enter the model context.

## Alternatives

Keep the loop in the API and pin the deployment to one replica. Rejected: that is the current limit, and it is not a production topology. Let the worker call built-in tools in process. Rejected: policy, approvals, wrapping, and secrets would have a second implementation.
