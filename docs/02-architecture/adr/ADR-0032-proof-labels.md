# ADR-0032: Proof labels

- Status: Accepted
- Date: 2026-11-10

## Context

Progress notes and the UI have called runs live, dry-run, scripted, and judged by a function named `llm_judge` that does not call a model. A reader cannot tell which result used the tenant's model.

## Decision

Only three labels are used in progress docs and in the UI.

| Label | Meaning |
|---|---|
| `unit` | In-process. No network and no model. |
| `contract` | Real HTTP and real Postgres. The model and third parties are stubbed. |
| `live` | The tenant's configured model endpoint. The report names the model id and the date. |

A dry-run gym is not `live`. `llm_judge` is renamed, or it calls a model. A rename that only measures lexical overlap is `not_judged` ([ADR-0029](ADR-0029-generic-judgements.md)), and the label is not `live`. Stage 7 applies this to the product and rewrites the progress record.

## Consequences

A green unit test is not evidence that a model agreed. A live report that omits the model id and the date is not `live`.

## Alternatives

Add a fourth label for the scripted gym. Rejected: the three labels already cover it (`unit` or `contract`). Keep the name `llm_judge` for an overlap score. Rejected: the name claims a model was called.
