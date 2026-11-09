# Tool-choice gym (platform verification, Layer 2)

The gym measures **accuracy**: given an instruction, does the agent loop pick the right
tool(s), with the right arguments, and ground its answer in the result? It runs the real
agent loop — scripted in dry-run (CI-stable), or against a real model when live.

## Suites

- **`tasks.yaml` → `../m33c-scorecard.md`** — the golden suite in **dry-run**, committed so CI
  can diff it. See [m33c-checklist](../m33c-checklist.md).
- **`accuracy.yaml` → `accuracy-scorecard.md`** — a harder suite where the instruction does
  **not** name the tool (the model must infer it) and several tasks need a **chain** of
  tools or a **recovery**. Meant for a **live** run; the scripted dry-run cannot solve it.

The live scorecards (`live-scorecard.md`, `accuracy-scorecard.md`) are written only under
`AR_EVAL_GYM_LIVE=1` and are **not committed** (they drift with the model); the durable
record of a live run is the finding written up below.

## Run it

```bash
make eval-gym                                    # golden suite, dry-run
# live golden:
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/m33c_eval_gym.py --live
# live accuracy suite (un-named / chains / recovery):
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... \
  uv run python scripts/m33c_eval_gym.py --live --tasks docs/testing/eval-gym/accuracy.yaml
```

The cert key is read from the environment and never printed. A chain is scored as an
ordered subsequence of the observed tool calls; the scorecard also breaks selection down
per tool.

## First live accuracy run (2026-11-09, Qwen3-32B) — the finding

**5/8 (62%).** The signal is the split:

- **Single-tool choice: 5/5 (100%).** From an un-named goal the model reliably picks the
  right tool — `general.code` for arithmetic, `general.fetch` for a page, `data.query` for
  the database, `knowledge.search` for a citation, `general.read_file` for an upload.
- **Chains: 0/3.** It does not compose tools well: it substituted `general.shell` for
  `general.write_file`, did a fetch-and-save task with **no tool call at all**, and solved
  the recovery task with `general.code` twice instead of `write_file`→`read_file` (the goal
  was reached, but not via the composed tools).

So **tool selection is strong; tool chaining is the weak spot.**

## Second pass (2026-11-09) — improving the chaining: 5/8 → 7/8 (88%)

The chain weakness turned out to be mostly setup, not the model. Three changes, each
measured live:

1. **The gym agent was not bound to `general.write_file`.** The file-chain tasks could not
   call the tool they needed, so the model substituted `shell` or `code`. Binding it made
   `acc-copy-token` and `acc-recover-missing` pass.
2. **Binding the whole file toolset hurt selection.** Adding `list_files`/`grep`/`glob`/… so
   the model had more options made it pick `general.list_files` over `knowledge.search` for a
   knowledge question — in both runs. Keeping the set to what the tasks need (just add
   `write_file`) recovered the knowledge task. **Tool-choice accuracy is sensitive to the
   tool set: bind what a task needs, not everything; a broad, overlapping set degrades
   selection.**
3. **Chains strained the budget.** A two-step chain against a live model hit the 60 s wall
   clock; raising it to 120 s (and `max_tool_calls` 4 → 6) let chains finish.

With all three, the accuracy suite is **7/8 (88%)**: every single-tool task and two of three
chains pass. The remaining failure, `acc-fetch-save`, is the model occasionally **narrating
its plan without calling a tool** (it passed, timed out, and narrated across three runs) —
a model-behaviour variance of Qwen3-32B, not a setup gap, and the honest residual to chase
with a stronger model or the agent loop. The tool-use prompt already says to prefer the
specific tool and not to work values out unaided; the gap is adherence, so it was not gamed.
