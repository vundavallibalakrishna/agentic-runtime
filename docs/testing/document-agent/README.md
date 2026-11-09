# Document agent proof — the real chat / agentic flows

`scripts/document_agent_proof.py` is the live half of the document verification. Where
`scripts/document_toolchain.py` drives each tool directly on a real input, this drives the
whole **agent loop**: a real model reads a natural-language instruction, chooses and chains
the document / spreadsheet / PDF / chart / OCR tools itself, and the **produced artifact** is
checked — not just which tool it picked.

It runs in process on the demo tenant with the `reasoning` alias pointed at the cert model
(the same live path the gym uses), so no running stack is needed.

## Run it

```bash
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY="$(cat /abs/.secrets/deepinfra_api_key)" \
  uv run python scripts/document_agent_proof.py
```

The cert key is read from the environment and never printed. `.secrets/` lives in the main
checkout, not in a worktree — reference it by absolute path. The per-run scorecard
(`docs/testing/document-agent/live-scorecard.md`) carries model output and is **gitignored**;
the finding below is the committed record.

## First live run (2026-11-09, `Qwen/Qwen3-32B`): **5/5**

| task (natural language) | tools the model chose | assertion on the output |
|---|---|---|
| "Build a spreadsheet from this CSV and tell me the total amount." | `documents.create` + `general.query_table` | the total in the answer is correct |
| "Create a one-page PDF titled 'Board Brief' whose body contains marker `VERIFYDOC4471`." | `documents.create` | **pypdf reads the marker back** out of the produced PDF |
| "Plot these quarterly figures as a bar chart." | `general.chart` | a valid PNG is produced |
| "Read the attached access note and quote the badge reset code." | `general.read_file` | the code is quoted in the answer |
| "A scanned image is attached — read the code it shows." | `documents.ocr` | the OCR'd code (`4821`) is in the answer |

**What this proves.** The real chat path turns a plain instruction into the correct document
outcome: the model picks a working tool, chains two when needed (create a workbook *and* query
it for the total), produces a real file that holds the asserted content, and reads an attached
file — a markdown note and a scanned PNG — to answer from it. The two attachment tasks go
through the real upload path (`store.upload`), so the conversation-attachment → workspace →
tool flow is exercised, not stubbed.

## Scope and limits

- Accuracy is for **one model** (Qwen3-32B); selection can vary per model, as the accuracy gym
  documents. The assertions here are on the **artifact**, so a task passes only when the output
  is actually correct, not merely because a plausible tool was called.
- This is a live proof, not a CI guard — it needs a model and a key. The deterministic
  regression guard is `scripts/document_toolchain.py` (see
  [`../document-toolchain/README.md`](../document-toolchain/README.md)).

## Grounded + vision operations (`scripts/document_grounded_proof.py`)

The agent proof above leaves the **model-backed** document tools untested, because the agent
might answer by reading rather than by calling them. This companion drives each directly
through the real `ToolPipeline` with the cert reasoning model — and, for `image.ask`, a real
vision model installed as the `vision` alias (the reasoning model cannot see images). Run:

```bash
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY="$(cat /abs/.secrets/deepinfra_api_key)" \
  uv run python scripts/document_grounded_proof.py
```

`AR_CERT_VISION_MODEL` overrides the vision model (default `Qwen/Qwen3-VL-30B-A3B-Instruct`,
served OpenAI-compatible by the same provider). The scorecard
(`grounded-scorecard.md`) is gitignored; the finding below is the committed record.

### First live run (2026-11-09): **4/4**

| op | input | assertion |
|---|---|---|
| `documents.summarise` | a report stating "Q3 revenue reached 42 million euros" | the figure appears in the grounded summary |
| `documents.extract` | an invoice (`fields: total due, due date`) | `4281.50` and `2026-02-15` are extracted |
| `documents.compare` | two policies differing only in the retention period | the change (7 → 10 years) is found |
| `image.ask` | a scanned image showing a code | the **vision model reads `4821`** from the image |

Reasoning: `Qwen/Qwen3-32B`. Vision: `Qwen/Qwen3-VL-30B-A3B-Instruct`.

### Finding: hand-rolled charts are not VLM-legible

A fifth, exploratory check asked `image.ask` to name the tallest bar in a `general.chart`
bar chart where one quarter (95) clearly dominates the others (20/35/50). The vision model
answered **Q1**, not Q2 — it read a value stamped on a scan fine, but could not compare bar
heights in the platform's hand-rolled chart PNG, which drew bars with no title, category
labels, value labels or gridlines.

**Resolved** (2026-11-09): `general.chart` now labels every chart — a title, gridlines with
y-axis tick values, a category label per bar, and the value on each bar — drawn from a new
pure-Python 5x7 bitmap font (`analytics/pixfont.py`), no plotting dependency added. On the
same chart the same vision model now answers **"Q2"** (tallest) and reads the **value "95"**
correctly. See `test_chart_fidelity.py`.
