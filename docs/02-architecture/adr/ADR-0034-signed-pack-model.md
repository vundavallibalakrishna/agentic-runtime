# ADR-0034: Signed pack model

- Status: Accepted
- Date: 2026-11-10

## Context

[ADR-0023](ADR-0023-pack-extensions.md) gives a pack six hooks and a separate Alembic history. The manifest shape, the trust rule, and the rule that core never imports a pack were not fixed tightly enough to keep an industry out of `apps/web` and out of core imports.

## Decision

A pack is out of process. Core never imports a pack. The manifest is signed camelCase JSON:

- `id`, `version`, `minCore`
- `permissions[]`, `auditActions[]`
- optional `schema` (the pack's own Alembic, via `packs/alembic_env.py`)
- `nav[]`, each item under `/packs/{id}/...`
- `tools[]`, `agents[]`, `skills[]`, `ruleSets[]`
- `connectors[]` (slugs only; secrets stay in core)
- `recognisers[]` (locale personal-data packs)

The UI hosts a pack in a generic `PackFrame`. `apps/web` has no industry routes.

Pack versions and rule-set versions are immutable. A judgement stores both.

An unsigned pack is refused outside development. Trust is `AR_PACK_TRUSTED_KEYS`. This refines ADR-0023.

## Consequences

Installing a pack registers its permissions, audit actions, and navigation. It does not add a route module to the web app. A connector slug in the manifest resolves to a secret the core secret store already holds. A locale recogniser pack adds personal-data patterns; core's default list does not grow to match one country.

## Alternatives

Load pack Python into the API process. Rejected: core would import the pack. A second, unsigned manifest for local packs in production. Rejected: production refuses unsigned packs.
