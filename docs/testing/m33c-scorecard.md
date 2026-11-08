# M33c tool-choice scorecard

Mode: `dry-run`.

Each task passes when the agent loop selected the expected tool, the arguments
matched, and the final answer is grounded in the tool result. `not_found` passes
only when the tool said the passage was missing and the answer does not invent it.
An approval task passes when the run is waiting and the answer does not claim success.

The dry-run mode replays a scripted model through the real agent loop and does not
call a paid provider. A live Qwen3-32B run is a separate file. See
`docs/testing/m33c-checklist.md`.

| Task | Tool | Args | Grounded | Pass | Note |
|---|---|---|---|---|---|
| general-code | pass | pass | pass | pass | 323 |
| general-shell | pass | pass | pass | pass | gym-shell |
| files-read | pass | pass | pass | pass | FILE-19 |
| fetch-page | pass | pass | pass | pass | FETCH-77 |
| http-post-approval | pass | pass | pass | pass | waiting_approval |
| data-query | pass | pass | pass | pass | paper |
| chart | pass | pass | pass | pass | 2 points |
| export-table | pass | pass | pass | pass | orders.csv |
| knowledge-cite | pass | pass | pass | pass | ZX-4471 |
| document-summarise | pass | pass | pass | pass | VAULT-42 |
| document-check | pass | pass | pass | pass | VAULT-42 |
| refuse-not-found | pass | pass | pass | pass | not_found |

Aggregate: 12/12 (100%).

## Per-tool selection

How often the model chose the expected tool (or chain), by tool.

| Tool | Selected | Rate |
|---|---|---|
| `data.query` | 1/1 | 100% |
| `documents.check` | 2/2 | 100% |
| `documents.summarise` | 1/1 | 100% |
| `general.chart` | 1/1 | 100% |
| `general.code` | 1/1 | 100% |
| `general.export_table` | 1/1 | 100% |
| `general.fetch` | 1/1 | 100% |
| `general.http` | 1/1 | 100% |
| `general.read_file` | 1/1 | 100% |
| `general.shell` | 1/1 | 100% |
| `knowledge.search` | 1/1 | 100% |
