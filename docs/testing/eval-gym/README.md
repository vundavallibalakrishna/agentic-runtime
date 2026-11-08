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

So **tool selection is strong; tool chaining is the weak spot.** Two things to note: the
model often prefers one powerful tool (`general.code`) over composing specific tools, and
strict chain scoring penalises an equally-valid alternative path — both are worth weighing
when this feeds tuning (prompting, tool descriptions, the loop). This is the measurement;
improving the chaining accuracy is downstream work.
