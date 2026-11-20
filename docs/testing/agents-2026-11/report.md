# Agents: building, configuring and the publish gate, 20 November 2026

This is the first of two passes over agents and orchestration ([plan](../../09-plan/progress.md)).
It covers building and publishing an agent, what an agent is configured with, and evals
and the publish gate. Every check ran through the public API on a staging-mode stack
(Postgres, Temporal, workers, gateways) with a real model, Qwen3.8-27B. The checks are in
[scripts/agent_certification.py](../../../scripts/agent_certification.py).

## Result

25 checks. 20 passed at the first run and 5 failed. Four of the five were product faults
and are fixed in the same change. The fifth was a check that tested the wrong person.

| Stage | Check | First run | After the fixes | What was seen |
|---|---|---|---|---|
| build | templates | pass | pass | 5 templates published and answered |
| build | builder | pass | pass | built from words and answered: 'I do not have information about your office opening hours on Sundays.' |
| build | edit-and-validate | pass | pass | edited, validated, and two bad definitions refused: definition is invalid |
| build | rollback | pass | pass | version 1 runs again; 3 versions are kept |
| build | bundle | pass | pass | exported, imported as ac-imported-1795168969-9, and it answers the same |
| build | visibility | pass | pass | private is the owner's alone; tenant is seen and run by a second person |
| build | disable-and-archive | pass | pass | disabled refused with: 'agent is disabled'; enabled again; still listed while archived |
| build | stale-edit | pass | pass | the second save from an old copy was refused with 412 |
| configure | tools | pass | pass | bound tool used and total right; with no tools bound nothing ran (completed) |
| configure | knowledge | pass | pass | found in the bound collection; an agent with no knowledge tool did not know |
| configure | skill | pass | pass | skill loaded (skills.load) and followed |
| configure | memory | pass | pass | memory on recalls in a new conversation; memory off does not |
| configure | output-schema | pass | pass | matching JSON returned; an impossible schema ended as failed |
| configure | budget | pass | pass | stopped at the tool-call limit after 2 calls and said so |
| configure | model-alias | pass | pass | runs on the named alias; an alias that does not exist is refused at publish |
| configure | computer | pass | pass | a command ran on the agent's computer and its output came back |
| configure | strict-grounding | pass | pass | answered from the file (with a citation); declined what is not in it |
| configure | ask-a-human | pass | pass | paused for a person, took the answer, and used it |
| configure | task-template | pass | pass | both template items answered from the file; an unknown template is refused |
| configure | pii-masking | fail | pass | the address in the file was not passed on: 'The document does not contain a supplier email address. The relevant passage reads:\n\n> "Th' |
| configure | knowledge-confined | fail | pass | the agent answered from its own collection and not from another |
| gate | eval-run | fail | pass | 1 case run and scored, pass rate 1.0, 1 result rows |
| gate | case-from-conversation | pass | pass | one case made from a reply, with 1 checks |
| gate | gate-holds-a-failing-change | fail | pass | a failing change was held (eval completed); a passing one went live |
| gate | gate-cannot-be-skipped-freely | fail | pass | refused with 403: 'skip_eval_gate requires agents:manage_all'; the earlier version still answers |

## What was wrong and what was changed

1. **No eval run could be carried out on a database-backed install.** The worker reads the
   run from the database. The agent it is for, its tags and its choice to replace every
   tool were kept only in the process that started it, so the worker failed on every run
   (`eval_run_failed`). A required suite therefore never let a publish through. The agent
   is now read through the version the run names, and migration 0059 stores the tags and
   the tool choice.
2. **An agent bound to one collection answered from another.** `knowledge.search` read
   every collection the person may read. An agent that binds collections now reads those
   and no others; one that binds none reads what the person may read (owner, 20 November).
3. **Masking did not cover an attached file's text.** With `safety.pii_masking` on, a
   document tool's result was masked, but the same text also reaches the model beside the
   message, unmasked. Both now pass through the same masking.
4. **The check for skipping the gate tested an administrator**, who may skip it. A plain
   publisher was already refused (`skip_eval_gate requires agents:manage_all`). That
   check lived in the route; it is now in the domain layer with the rest of publishing,
   and a publish that passed over a required suite says so in its audit entry.

## Seen and not changed

- An archived agent is still in the list of agents.
- An agent made without a `tools` list gets the default set of tools. An empty list gives none.
- Only the first required suite of an agent is run before a publish (`_gated_publish`).
- The stack's sign-in cookie is marked secure, so a browser on plain http cannot hold a
  session on a staging-mode stack run on one machine.

## Second pass: agents that call each other

Eight checks (`--stage together`) on the same stack. Four passed at the first run; all
eight pass after the fixes.

| Check | First run | After the fixes |
|---|---|---|
| A lead asks one specialist and passes on the answer | pass | pass |
| A lead asks three specialists at once | pass | pass |
| Two agents set up to call each other | pass (refused at publish) | pass |
| A slow specialist is given up on, and the lead says so | pass | pass |
| The person's conversation holds only their own messages | fail | pass |
| Handoff ends the lead's turn | fail (15 handovers) | pass (one) |
| Stopping the lead stops its specialist | fail (left running) | pass |
| A specialist whose action needs approval | fail (internal error) | pass (refused in words; approved and run when asked directly) |

What was wrong and what changed is in [OQ-157](../../open-questions.md).
