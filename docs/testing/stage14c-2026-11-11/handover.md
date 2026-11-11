# Handover: Stage 14c, live-certification blockers

Date: 11 November 2026. Branch `fix/stage14c-live-cert-blockers`, from `aec5402b`. Not pushed.

## What landed

| Blocker | Cause | Fix |
|---|---|---|
| Research ended in "The worker lost this turn" | Research mode lived only in memory. A reload replaced the checkpoint with an untracked dict, so sub-task results were never saved. The step limit left the run working. | Research is read from `runs.trigger`. `TrackedRow.update` keeps merged values tracked and a reload does not mark rows changed. The step stores the results the workflow hands it. The step limit ends the run `failed` (`budget_exceeded`, `max_steps`). Research activities heartbeat. |
| The CSV chart was never drawn | The assistant was not granted `general.chart`. A grant added in process memory was lost when the worker reloaded the version. The chart tool took only inline rows. | Revision `0044` publishes the seeded assistant again with the chart and table tools. `general.chart` reads a table file by `path`. A script that imports a missing package is told to call the chart tool. In tool-search mode the first call is offered the tools closest to the request. |
| Eval pass rate 43% | The certification scored bare model calls with no agent, tools or context. | The certification starts an eval run in the product from `evals/live/certification.yaml`. `scripts/eval_run.py` has no live mode. |
| UI nits | Screenshots were taken before the upload. The Computer pane never read a text file's content. Generated files were typed from a short hand-written table. | Screenshots come last and wait for a loaded page. Previews read the file content, with loading, empty and error states. One name-to-type helper serves both writers. |

## Proof

Live means the local stack on this branch, Postgres on 5433, Temporal on 7234, model `Qwen/Qwen3-32B` on DeepInfra, 11 November 2026.

| Check | Result | Proof |
|---|---|---|
| Research run, cert question | completed in about 2 s, 2 sources | live |
| `/v1` chart, plain request | `general.chart` called, PNG image part | live |
| CSV attached in chat, "draw a bar chart" | `chart.png` drawn, 3 of 3 runs | live |
| Chart shown in the web chat and Computer pane | seen in a real browser | live |
| Certification eval suite | 8 of 8 cases, gate passed | live |
| Screenshots step, `/documents` lists uploads | passed | live |
| Text and HTML previews, file types | content shown, `text/plain` and `text/html` | live |
| Python unit suite | 1,351 pass, 4 fail | unit |
| Web unit suite | 84 pass | unit |

The 4 unit failures were not caused by this change: two Qdrant conformance tests need a Qdrant container, `test_fixtures_agree_with_opa` fails on this machine, and `test_m38b_e2e_harness` reads a port from the local environment. None was checked against main.

## Not done

- The full `scripts/certify_live.sh` was not run. It needs the second user's password and the provider key in the shell.
- The integration suite, the web end-to-end job, the kind jobs and `make gen` in full were not run. `gen_openapi.py` and `gen_json_schema.py` were run and changed nothing.
- Revision `0044` was applied to the local database on 5433. Its upgrade was not run inside the integration migration test.

## Open, for the owner

1. Research searches a built-in `fixture` provider by default and falls back to it silently. The report is canned text, not the tenant's documents. See OQ-130.
2. A replayed tool call returns a preview and no structured result. Research refuses to count it; the general fix is to keep the result.
3. `scripts/eval_run.py` and `ar_domain/evals/harness.py` remain as a stub contract check beside the product eval runner.
4. Built-in tool text changed by a release is applied in memory only, because approved tool versions cannot change.
5. Eval conversations appear in the recent chats of the person who started the eval run.

## How to run

```bash
cd .claude/worktrees/stage14c
set -a; . ./.env; set +a
uv run --no-sync alembic -c libs/ar_domain/alembic.ini upgrade head
UV_NO_SYNC=1 uv run --no-sync honcho start -f Procfile.dev
```

The API is on 18010 and the web app on http://localhost:3000. Sign in as `admin@dev.local`.

## How to test visually

1. Open http://localhost:3000 and sign in.
2. Start a new chat, attach a CSV with a text column and a number column, and send "Draw a bar chart of count by region". Expect a PNG bar chart in the reply and in the Computer pane, and "Answered by Qwen3-32B".
3. Ask "Write notes.txt with one line and report.html with a heading". Expect both files in the Computer pane, the text file showing its line and the HTML file showing its source.
4. Reload the page. Expect the chart, the files and the model label to remain.
5. Open Documents. Expect the uploaded documents to be listed.
