# Live certification

Proof label: `live` only when this run used the tenant's model. The report names the model id and the date. A run without `AR_LLM_API_KEY` writes a scorecard labelled `contract` and leaves the live run pending. It does not invent a model id.

The kind job (`scripts/stage9_kind_contract.sh`) is `contract`. It installs the chart with 2 API replicas and 2 workers and uses fake-llm.

## Ports

The owner's Postgres is on host port **5433**. Do not bind 5432, 6379, 7233, 8000 or 8013. The script exits if a URL uses one of those ports.

| Service | Host port |
|---|---|
| Postgres | 5433 |
| Valkey | 6380 |
| Temporal | 7234 |
| API | 8010 |
| Web | 3000 |
| mcp-gateway | 8002 |
| sandbox-manager | 8003 |
| system worker | 8014 |

## Command

From a checkout, with the stack already up and a real document on disk:

```bash
export AR_DATABASE_URL=postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5433/agentic_runtime
export AR_VALKEY_URL=redis://127.0.0.1:6380/0
export AR_TEMPORAL_ADDRESS=127.0.0.1:7234
export AR_API_URL=http://127.0.0.1:8010
export AR_WEB_URL=http://127.0.0.1:3000
export AR_LLM_BASE_URL=https://api.deepinfra.com/v1/openai
export AR_LLM_MODEL=Qwen/Qwen3-32B
export AR_LLM_API_KEY=...          # never commit this
export AR_ADMIN_EMAIL=admin@dev.local
export AR_ADMIN_PASSWORD=...
export AR_SECOND_EMAIL=reviewer@dev.local
export AR_SECOND_PASSWORD=...
export AR_CERT_DOCUMENT=/path/to/a-real-document.txt
export AR_CERT_OUT=var/live-certification
bash scripts/certify_live.sh
```

The scorecard is `var/live-certification/scorecard.json`. Playwright screenshots are `var/live-certification/screenshots/`. Both name the model id and the date when the label is `live`.

## What the run does

1. Sign in through the UI and screenshot the home page.
2. Open the agent builder and create an agent.
3. Upload `AR_CERT_DOCUMENT`.
4. Run `documents.judge` with a rule set.
5. Send a chat turn that calls a tool through mcp-gateway.
6. Approve a four-eyes request as the second user.
7. Read the audit chain and run `scripts/verify_audit_chain.py`.
8. Start a research run and read it back. The report cites stored pages. Each source has `sha256` and `fetchedAt`. This step uses the fixture provider unless a search secret is configured. It does not invent a search-provider result.
9. Run `scripts/eval_run.py --live` against `AR_LLM_BASE_URL`. The scorecard records the model id, the date and the summary. A missing key leaves this step pending and the label stays off `live`.
10. Send a chat turn with `researchMode` false and confirm the run trace can include `endpointId` when model routes are configured. No API key is written into the scorecard.
11. Probe each connector whose token is set: `AR_CERT_SLACK_TOKEN`, `AR_CERT_GOOGLE_TOKEN`, `AR_CERT_MICROSOFT_TOKEN`, `AR_CERT_ATLASSIAN_TOKEN`, `AR_CERT_GITHUB_TOKEN`, `AR_CERT_REST_TOKEN` with `AR_CERT_REST_URL`. A missing token records the step as pending and does not invent a provider result. The scorecard stays off `live` only when a provided token fails.
12. When `AR_CERT_OCR_GOOGLE`, `AR_CERT_OCR_AWS` or `AR_CERT_OCR_AZURE` is set, post one page to that named endpoint. Otherwise the OCR step is pending.
13. When `AR_GREENMAIL_SMTP` is set, send one notice through that SMTP server. Otherwise the mail step is pending. CI does not pull GreenMail.

A step that does not succeed keeps the scorecard off `live`. A pending connector, OCR or mail step is not a failure.
