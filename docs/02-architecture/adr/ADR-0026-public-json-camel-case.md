# ADR-0026: Public JSON is camelCase

Date: 2026-10-20. Status: Accepted.

## Context

API examples were snake_case, matching Python and Postgres. The UI is TypeScript. Showing `created_at` in the product and in generated types fights the presentation bar and makes every form map names by hand.

## Decision

Public JSON property names are camelCase. Python attributes stay snake_case. One base model, `ar_contracts.api_model.ApiModel`, sets `alias_generator=to_camel`, `populate_by_name=True`, and `serialize_by_alias=True`. Generated JSON Schema, TypeScript, and Zod use the aliases. `scripts/check_public_camel_case.py` fails the docs CI job when a public schema property is not camelCase.

Database columns, SQL, environment variables, log keys, and metric names are unchanged.

Internal HTTP (`/internal/v1`) stays snake_case so workers are not forced through the UI contract.

These identifier grammars stay as already catalogued, because they are tokens rather than object keys: permission keys, audit actions, error `code` values, stream `type` values, and enum string values already fixed in `ar_contracts` (`waiting_approval`, `max_steps`, `in_progress`). The UI shows a label, not the raw token.

## Consequences

- Spec prose may still say `created_at` for the column and the Python attribute. The JSON name is `createdAt`.
- Definition YAML edited in the UI uses camelCase keys. The server accepts snake_case keys on input so older files still import.
- M1 response models subclass `ApiModel` ([M1-T16](../../09-plan/M01-foundation.md)).

## Alternatives

- Snake_case end to end, including TypeScript. Rejected: it leaks into the UI.
- camelCase in Python as well. Rejected: it breaks the language and the database.
- Hand-written aliases per field. Rejected: they drift.
