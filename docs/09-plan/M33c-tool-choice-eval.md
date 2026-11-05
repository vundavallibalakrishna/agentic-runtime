# M33c — Tool-choice eval gym

Measure whether a model calls the right tool and whether the final answer matches the tool result, including an honest `not_found`. Qwen3-32B sometimes answers with no tool call or invents a result. This gym turns that into a regression number.

Parallel work owns segregation of duties, fetch and search product changes, OCR and vision, and Office file creation. This milestone does not implement those.

## M33c-T01 · Harness, goldens and scorecard

- **Depends on:** M32-T01
- **Areas:** `docs/testing/eval-gym/`, `libs/ar_domain/src/ar_domain/evals/gym/`, `scripts/m33c_eval_gym.py`
- **Do:** Golden tasks for `general.code`, `general.shell`, workspace files, `general.fetch`, approval-gated `general.http`, `data.query`, chart and export, a knowledge citation, document summarise and check, and one case that must say `not_found`. A dry-run scripted model drives the agent loop with no paid call. `AR_EVAL_GYM_LIVE=1` plus `AR_CERT_LLM_API_KEY` runs Qwen3-32B. Default CI runs only the dry-run.
- **Done when:** `uv run pytest libs/ar_domain/tests/unit/test_m33c_eval_gym.py` passes without a model key, and `docs/testing/m33c-scorecard.md` shows the dry-run aggregate.
- **Tests:** `libs/ar_domain/tests/unit/test_m33c_eval_gym.py`

How to run: [m33c-checklist](../testing/m33c-checklist.md).
