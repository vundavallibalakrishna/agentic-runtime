# M33c checklist — tool-choice gym

The gym asks whether the model picks the right tool and whether the answer matches the tool result. Default CI runs a scripted model through the real agent loop. A paid model runs only when you set the live flag.

## CI, no model key

The unit test and `make eval-gym` do not read `AR_CERT_LLM_API_KEY`. A key sitting in the environment is ignored until `AR_EVAL_GYM_LIVE=1`.

```bash
uv run pytest libs/ar_domain/tests/unit/test_m33c_eval_gym.py -q
make eval-gym
```

`make eval-gym` rewrites `docs/testing/m33c-scorecard.md`. The dry-run aggregate is 12/12. Proof is `unit`. That number measures the scripted model plus the real tools (code, shell, files, the fetch fixture, approval hold, SQL, chart, export, knowledge, documents). It is not a live model score. A live run writes `docs/testing/eval-gym/live-scorecard.md` and names the model id and the date.

## Live Qwen3-32B on DeepInfra

Set both the flag and the existing cert key. The key is not printed and is not written into the scorecard.

```bash
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/m33c_eval_gym.py
```

Optional overrides:

- `AR_CERT_LLM_BASE_URL` defaults to `https://api.deepinfra.com/v1/openai`
- `AR_CERT_LLM_MODEL` defaults to `Qwen/Qwen3-32B`

The live scorecard is `docs/testing/eval-gym/live-scorecard.md`. It is gitignored. Fetch and HTTP stay on the in-process fixture for `https://example.com/gym`, so the live run spends tokens on the model and does not call the public web. A POST still waits for approval and is not sent.

`--live` without `AR_EVAL_GYM_LIVE=1` exits 2 and does not call the provider. The flag without the key also exits 2.

## What each row means

| Column | Pass when |
|---|---|
| Tool | The agent loop called the expected tool |
| Args | The matching call's arguments contain the expected values |
| Grounded | The answer quotes the tool result, or the run is waiting for approval and does not claim success, or both the tool and the answer say `not_found` and the answer does not invent the missing fact |

Tasks live in `docs/testing/eval-gym/tasks.yaml`. The scripted chooser is `ar_domain.evals.gym.policy` and does not read the expected tool from that file.

## Out of scope

Segregation of duties, new fetch or search behaviour, OCR, vision, and Office file creation belong to other tracks. This gym only scores the tools that already exist.
