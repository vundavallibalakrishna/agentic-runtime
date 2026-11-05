# M36 run guide

The dry command is the one CI runs. It does not call Slack, GitHub, or any other provider.

```bash
make live-pack
uv run pytest libs/ar_domain/tests/unit/test_m36_live_pack.py -q
```

Expect every row to say `skipped` and `dry`. GitHub's catalog column stays `live`. The other connectors stay `not_live` or `public` (S3). `docs/testing/m36/ledger.json` still has an empty `rows` array.

## Screen

Start the stack the usual way (`make up`, `make migrate`, `make seed`, then the API and the web app). Sign in as `admin@dev.local` and open Connectors.

Each card shows **Built** and a second badge: **Live-tested**, **Tested on the provider API**, or **Not live-tested**. The line under the search box says built means the tools are in the product, and live-tested means a canary called the provider. Notion, Slack and AWS show Not live-tested. GitHub shows Live-tested. S3 shows Tested on the provider API. Open Google Calendar and the setup steps include pasting a bearer token. Open SharePoint and the steps say the tools call the signed-in OneDrive. Open Teams and the steps say the read lists channels and does not read message text.

## One live read

Export a token in the shell. Do not put it in a file in this repo.

```bash
AR_M36_LIVE=1 AR_M36_ONLY=github uv run python scripts/m36_live_pack.py
```

The GitHub row is `live` when `https://api.github.com` answers for `octocat/Hello-World` `README`. No token is required for that public read. Add `--record` only after you have read the report. The ledger must not contain a token. If it does, the writer refuses the row.

## One approved write

Leave this unset in CI.

```bash
AR_M36_LIVE=1 AR_M36_WRITE=1 AR_M36_WRITE_APPROVED=1 \
  AR_M36_ONLY=github \
  AR_M36_GITHUB_TOKEN=... \
  AR_M36_GITHUB_OWNER=... \
  AR_M36_GITHUB_REPO=... \
  uv run python scripts/m36_live_pack.py
```

Without `AR_M36_WRITE_APPROVED=1` the write column is `awaiting_approval` and no issue is opened. The same gate covers every connector that has a write. Okta deactivate runs only when `AR_M36_OKTA_USER_ID` is set as well.

Variable names are listed in [m36-checklist](m36-checklist.md).
