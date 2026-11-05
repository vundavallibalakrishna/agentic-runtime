# M32 follow-up fixes (5 Nov 2026)

Defects left by the hardening merge (`123cf366`, PR 49). Phase 2 store retirement is unchanged.

## What changed

- `requestOptions` keeps provider keys such as `chat_template_kwargs` on GET and POST.
- Durable hydrate drops the in-memory `fake-llm` / `reasoning` rows when Postgres already has those names.
- Redaction leaves `/workspace/…`, `…/ar-sandboxes/…`, and UUIDs inside tool text alone.
- The run token budget adds prompt growth and output. Usage and cost still record the full provider counts. The assistant cap stays 16,000.
- Chat SSE sends a `: ping` comment every 10 seconds while the run is active. The stream is not rewritten onto Valkey.
- Pytest ignores an `AR_OPA_URL` that arrived only from `.env`. An exported `AR_OPA_URL` still wins.

## Alembic

Main's revision `0032` (`20261105_0032_model_request_options`) adds `models.request_options` and drops it on downgrade. It revises `0031`. Main's `0033` (`20261105_0033_durability`, M35) follows it and is the single head.

## Checks run

On this branch, in the cloud environment:

- `uv run mypy` — clean, 627 files, including `identity/seed.py`.
- `uv run alembic -c libs/ar_domain/alembic.ini heads` — single head `0032`.
- Targeted pytest — 48 passed (`test_m32_usage_cost`, `test_m32_analysis`, `test_m32_model_options`, `test_m32_catalogue_dedupe`, `test_chat_service`, `test_m21_loop`, `test_public_json`, `test_m32_request_options`, `test_opa_env`, `test_m2_api`).

```bash
uv run pytest libs/ar_domain/tests/unit/test_m32_usage_cost.py \
  libs/ar_domain/tests/unit/test_m32_analysis.py \
  libs/ar_domain/tests/unit/test_m32_model_options.py \
  libs/ar_domain/tests/unit/test_m32_catalogue_dedupe.py \
  libs/ar_domain/tests/unit/test_chat_service.py \
  libs/ar_domain/tests/unit/test_m21_loop.py \
  libs/ar_contracts/tests/unit/test_public_json.py \
  services/api/tests/unit/test_m32_request_options.py \
  services/api/tests/unit/test_opa_env.py \
  services/api/tests/unit/test_m2_api.py -q
uv run mypy
uv run alembic -c libs/ar_domain/alembic.ini heads
```

A live model round trip was not run here. DeepInfra keys are not available in this environment. Host Postgres, Redis, Temporal, and the apps on 8000/8013 were left alone.
