# Policy watch pack: run on a real site with a real model

23 November 2026. The pack at `packs/examples/policy-watch` was installed on an empty tenant of a
database-backed install in staging mode (Postgres, Temporal, Valkey, the object store, the OPA
sidecar, the tool gateway and the model gateway as separate processes) and its routine was run
five times with the model the install uses for certification, through DeepInfra.

## What was watched

| Source | Kind | Why |
|---|---|---|
| `https://www.rbi.org.in/notifications_rss.xml` | feed | The pack's shipped source: a real public feed |
| `https://www.rbi.org.in/Scripts/NotificationUser.aspx` | page | The pack's shipped source: a real public page |
| A page served on the test machine | page | Added to the skill's source list for this run, so its content could be changed between two runs |

## Result

| Run | Situation | Status | Time | Tool calls | Tokens in | What the agent did |
|---|---|---|---|---|---|---|
| 1 | First run on an empty tenant | completed | 160 s | 21 | 246,109 | Stored a first copy of both pages and of the feed items; reported them as a baseline, not as changes |
| 2 | Nothing changed | completed | 52 s | 14 | 48,769 | "No material change on 3 sources." It saw that the real RBI page had changed in a navigation label and a file-size unit, and judged that not to matter |
| 3 | Test page changed (limit, reporting period, new section) | completed | 63 s | 8 | 47,139 | Reported the three changes with the words before and after, wrote the digest, ended "Needs acknowledgement". It also said the RBI page was unchanged without having read it in that run |
| 4 | Nothing changed, pack 1.0.1 | completed | 69 s | 11 | 83,607 | Read all three sources in the run; "No material change on 3 sources." |
| 5 | Test page changed (effective date, section removed), pack 1.0.1 | completed | 74 s | 10 | 48,681 | Read all three sources in the run; reported the new date and the removed section with quotes, wrote the digest, ended "Needs acknowledgement" |

| 6 | Started by the schedule itself at 13:00 India time, nothing changed | completed | not timed | 10 | not recorded | Read all three sources; reported no change that matters. It wrote a digest document and a longer answer where the instructions ask for one line |

Runs 1 to 5 were started by hand with `POST /api/v1/routines/{id}:run`. Run 6 was started by
the routine's own schedule, on the Temporal clock, with nobody asking.

Every run stayed inside the agent's budget (40 steps, 60 tool calls, 400,000 tokens).

What this shows: the routine reads a real feed and real pages, keeps a copy of each, compares a
changed page with the copy before it, tells a change that matters from one that does not, quotes
the words before and after, and stays quiet when nothing matters. It also shows the installed
pack being refused unsigned, installed signed, upgraded, and its routine arriving paused.

## Faults found, and what was done

Fixed in the product, with tests (their own pull request):

1. **A routine's tool calls all failed on an install with the policy sidecar.** The question
   sent to OPA carried the routine's id as a value that cannot be encoded as JSON. A development
   install asks the policy in process and never encodes it, so only a staging or production
   install was affected.
2. **A routine's run was given the workflow's default of eight steps.** The routine path built
   its own start payload without the step allowance a chat turn is given, so a routine whose
   agent used more than about four tools ended with "The agent could not finish this reply".
3. **An installed pack was not saved.** The install worked, but the pack was not in the list
   afterwards and could not be upgraded or removed, because its rows stayed in the memory of the
   request that installed it.

Fixed in the pack:

4. **A claim without a check.** In run 3 the agent said the RBI page was unchanged, and it had
   not read that page in that run. The instructions now say that a source counts as checked only
   when a tool was called on it in the same run. Runs 4 and 5 read every source.

Open in the pack:

5. **A quiet run is not always one line.** Of the four runs with nothing to report, two
   answered in one line and two added detail; run 6 also wrote a digest document. Nothing false
   was said, but an install that mails every result would get more than it should. The wording
   of the quiet-run rule needs another pass against the model.

Open, recorded in [open-questions](../../open-questions.md) (OQ-180):

- A routine's daily run limit, budget and overlap rule cannot be changed after it is created;
  the update endpoint takes only the name, description, instructions, agent, trigger and
  delivery. For this run the limit was raised directly in the test database.
- When a turn runs out of workflow steps the run ends as `internal_error` with no reason
  recorded on the run and nothing in the worker's log.
- The page on the real site changes a navigation label and a unit between requests. Each
  variant is stored once, so this costs two stored copies, not one per run.

## How it was run

- A clean tenant, seeded with `scripts/seed_tenant.py`; the model provider, model and aliases
  registered through the API.
- The tenant's allowed hosts set to the three hosts above, through the API.
- The pack installed with `POST /api/v1/content-packs:install`. Unsigned it was refused
  (`pack_signature_invalid`). It was then signed with a key made for this run and trusted only
  by this install.
- The skill and the agent published and the routine resumed through the API, then each run
  started with `POST /api/v1/routines/{id}:run`.
- Not running: the sandbox manager, the channels service and the two connector servers, which
  the pack does not use.

## Not covered

- A delivery by email or webhook, and the approval that goes with it. The pack ships with
  delivery to its owner's conversation only.
- The customer's own policy collections: none was named, so the step that searches them was
  skipped in every run.
- A licensed feed.
