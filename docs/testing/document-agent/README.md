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
- The LLM-backed grounded operations other than OCR/read (`documents.summarise`, `compare`,
  `extract`) and `image.ask` (which needs a vision-capable alias the cert model does not
  provide) are not yet asserted here; they are candidates for the next pass once a vision model
  is configured.
- This is a live proof, not a CI guard — it needs a model and a key. The deterministic
  regression guard is `scripts/document_toolchain.py` (see
  [`../document-toolchain/README.md`](../document-toolchain/README.md)).
