# ADR-0029: Generic judgements

- Status: Accepted
- Date: 2026-11-10

## Context

Document checks were described as comparing a file with a named standard. Naming a standard in core, including in a test or a sample prompt, picks an industry. A buyer's checklist is content they supply, not a behaviour of the platform.

## Decision

A **rule set** is versioned content:

- `id`
- `version`
- `items[]`, each with `itemId` and `statement`
- `sourceFileId` and `sha256` of that file

A **judgement** records the rule-set version, the item id, the verdict, the passage id, the quote, the model id, and the prompt hash.

A quote that is not a substring of the stored passage is `not_supported`. Lexical overlap is `not_judged`. It is never a verdict.

Core never names a framework, including in tests. The tenant's rule set carries the statements. Stage 5 stores the tables.

## Consequences

Two judgements of the same passage can disagree only by quoting different text or by using different rule-set versions. Both versions are stored on the judgement, and a published version is immutable. A model that fails schema validation produces a failed judgement, not a guessed verdict.

## Alternatives

Bake one standard's control list into core. Rejected: that is an industry. Treat word overlap as a passing verdict. Rejected: overlap is not support, and it must not be reported as one.
