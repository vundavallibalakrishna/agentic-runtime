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

**Do:** suites under `evals/` run the real loop and tools. The echo reply is removed.

## M42-T04 Chat shows a tool at work

**Do:** a card appears when a tool starts, with its arguments. A failure shows its code and message.

## M42-T05 Approve in place

**Do:** the approval card in chat has approve and reject, for a person who may decide it.

## M42-T06 Tokens stream

**Do:** model tokens reach the client as they are produced.

## M42-T07 A trace worth reading

**Do:** the run page shows each call's arguments, result, timing and the step that made it.
