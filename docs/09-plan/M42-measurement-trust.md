# M42 — Measurement and trust

Goal: tool choice and chaining are measured on real models, and a person can see what a tool is doing.
Source: [the tool review](../testing/tools-review-2026-11-05/tools-review.md), section C.

Depends on: M38. M42-T01 to T03 can start after M38. The tasks that show browser and document work wait for
M40 and M41. Tasks are split into full task entries when the milestone starts.

## M42-T01 Gym tasks that need a chain

**Do:** tasks that need two or more tools in order, tasks that recover from a failed call, tasks with a large
result, and tasks that do not name the tool.

## M42-T02 A live scorecard for each model

**Do:** the gym runs against a registered model on a schedule. The scorecard for each model is committed.

## M42-T03 The eval runner runs the agent

**Do:** M38a-T02 makes an eval run call the agent loop. This task rewrites the suites under `evals/` so that they assert on what a real model and real tools produce. Until then `evals/golden/assistant.yaml` still asserts that the reply repeats the question, which only a scripted model does, so `make eval` against a real model fails those cases.

## M42-T04 Chat shows a tool at work

**Do:** a card appears when a tool starts, with its arguments. A failure shows its code and message.

## M42-T05 Approve in place

**Do:** the approval card in chat has approve and reject, for a person who may decide it.

## M42-T06 Tokens stream

**Do:** model tokens reach the client as they are produced.

## M42-T07 A trace worth reading

**Do:** the run page shows each call's arguments, result, timing and the step that made it.
