# ADR-0005: In-house thin OpenAI-compatible model gateway

- Status: Accepted
- Date: 2026-10-20

## Context

Companies run their own models (vLLM, TEI, other OpenAI-compatible servers). We need per-tenant aliases, fallbacks, circuit breakers, quotas, metering and kill switches with tenant context from internal JWTs.

## Decision

Build `model-gateway` (FastAPI, `openai` client to upstreams) implementing `/v1/chat/completions`, `/v1/embeddings`, `/v1/rerank`, `/v1/models`, `/v1/tokenize` with alias resolution from the `models` module ([spec 04](../../03-specs/04-model-gateway.md)).

## Consequences

Small surface (~1.5k lines), native tenant/quota integration, no extra database. Cost: provider-specific adapters must be written if non-OpenAI-compatible providers are required (out of scope v1: all supported engines speak the OpenAI API).

## Alternatives considered

Third-party LLM proxies (rejected: separate config/DB model, harder tenant-aware quotas and kill switches, larger attack surface).
