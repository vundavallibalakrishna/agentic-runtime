# ADR-0022: Run records are sealed recordings, not bit-reproducible regeneration

- Status: Accepted
- Date: 2026-10-20

## Context

An auditor asked to re-perform a control test must see the agent version, prompts, model, retrieved chunks and tool inputs and outputs that produced a result. Temporal replays workflow code deterministically. It does not make model output bit-for-bit reproducible. Content capture in telemetry is off by default in SaaS.

## Decision

Record mode is opt-in per agent (`output` stays as specified; the flag is `spec.assurance.record_mode`, default `off`). GRC pack templates default it to `on` ([OQ-29](../../open-questions.md)). When it is on, finishing a run seals a run record: agent version and definition hash, prompt-template hashes, model id and any revision or weights digest the provider returned, sampling parameters, retrieved chunk ids and `index_version`, output hash, and the tool arguments and results encrypted as one evidence item. Re-performance replays with the recorded tool results and the pinned model, and reports divergence. The product does not claim that a second model call returns the same tokens. Normative behaviour: [spec 18 §7](../../03-specs/18-observability-eval.md#7-run-records-and-re-performance).

## Consequences

Recorded runs cost storage in the evidence vault, bounded by `AR_RUN_RECORD_MAX_BLOB_BYTES` and the record's retention class. Replay is an explicit, audited action. Eval publish gates can require a groundedness grader without requiring record mode.

## Alternatives considered

Relying on Temporal history alone (rejected: histories are not an auditor-facing manifest and are not signed). Promising deterministic regeneration with temperature 0 (rejected: open-weight models still differ across hardware and batch sizes).
