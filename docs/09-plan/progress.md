# Progress

One line per task: `id | status | commit | notes`.

M0-T01 | done | 820e3dd | monorepo skeleton
M0-T02 | done | 820e3dd | pins re-verified 2026-10-20
M0-T03 | done | 820e3dd | ar_common core
M0-T04 | done | 820e3dd | clients, telemetry, internal JWT
M0-T05 | done | 820e3dd | HTTP template and service mains
M0-T06 | done | 820e3dd | compose stack
M0-T07 | done | 820e3dd | fake-llm
M0-T08 | done | 820e3dd | web skeleton
M0-T09 | done | 820e3dd | codegen, including Zod from Pydantic and CLAUDE.md from AGENTS.md
M0-T10 | done | 820e3dd | CI
M0-T11 | done | 820e3dd | images
M0-T12 | done | 820e3dd | ar_testing fixtures

M1-T01 | done | 6a865cb | database core, tenant session, repository
M1-T02 | done | 6a865cb | Alembic revisions 0001-0005; CI migrations job
M1-T03 | done | 6a865cb | identity schema, permissions, idempotent seed
M1-T04 | done | 6a865cb | RLS and cross-tenant integration tests
M1-T05 | done | 6a865cb | append-only audit hash chain
M1-T06 | done | 6a865cb | outbox, relay decisions, idempotency middleware
M1-T07 | done | 6a865cb | secret metadata API and encrypted/vault stores
M1-T08 | done | 6a865cb | OIDC BFF login, session, CSRF, step-up
M1-T09 | done | 6a865cb | request pipeline, permissions, rate limits
M1-T10 | done | 6a865cb | tenant, users, invitations, groups, teams, me
M1-T11 | done | 6a865cb | roles, service accounts, API keys, audit read
M1-T12 | done | 6a865cb | domains, identity providers, SCIM
M1-T13 | done | 6a865cb | tenant provisioning plan, platform admin, signup
M1-T14 | done | 6a865cb | notifications, webhooks, signed camelCase bodies
M1-T15 | done | f60357c | sign-in page and admin users shell
M1-T16 | done | adf0e2d | public JSON via ApiModel; requestId; GET /me displayName and createdAt

M2-T01 | done | 1460d56 | model registry, migration 0006, SSRF allow-list
M2-T02 | done | 1460d56 | usage events, daily rollup, migration 0007
M2-T03 | done | 1460d56 | model-gateway breaker and parameter merge
M2-T04 | done | 1460d56 | definitions and stream contracts already in ar_contracts
M2-T05 | done | 1460d56 | agents registry, migration 0008, published assistant
M2-T06 | done | 1460d56 | conversations and runs, migration 0009
M2-T07 | done | 1460d56 | files API, scan decisions, migration 0010
M2-T08 | done | 1460d56 | in-process SSE with per-user cap
M2-T09 | done | 1460d56 | agent run advance for model steps only
M2-T10 | done | 1460d56 | runs API and signed callback helper
M2-T11 | done | 1460d56 | web chat with streaming, empty and error states
M2-T12 | done | 1460d56 | regenerate, edit, branches, feedback, share, export
M2-T13 | done | 1460d56 | models admin and dev login without an external key

M2.5-T01 | in_progress | - | design system, shell, sign-in, chat, restyled pages
M2.5-T02 | in_progress | - | Keycloak callback and local-run bugs
M2.5-T03 | in_progress | - | fresh-clone CI job
M2.5-T04 | in_progress | - | checklist, screenshots, walkthrough
