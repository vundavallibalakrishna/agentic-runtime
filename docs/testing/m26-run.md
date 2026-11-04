# M26 run guide

Use ports that are not already taken. Do not stop Postgres, Temporal, Redis or the apps on 8000, 8001 and 8013.

```bash
cp .env.example .env
# Point AR_PORT, AR_WEB_HOST_PORT and AR_PG_HOST_PORT at a free block.
make ports-check
make up
make migrate
make seed
honcho start -f Procfile.dev
```

`AR_GRC_PACK_ENABLED` stays unset or `false`.

Sign in with dev sign-in as `admin@dev.local`.

## Catalog

Open Connectors. Search for a product and filter by category. Each card shows a badge: Live-tested, Tested on the provider API, or Not live-tested. The note under the badge says what that means.

Open a connector. The page lists the setup steps, a link to the provider's app page, the scopes, and each tool. Writes say "Asks first".

Connect and install. The secret field is a password input and the saved page does not show it. Test connection reports success or a message you can act on (401 reconnect, 403 scopes, 404 not found, 429 retry-after). Turn a tool off and it stays off for that install.

On an agent, open Advanced, then the tools section. Connector tools can be attached one by one. A write still waits for approval in chat.

## Honest labels

GitHub reads can use the public API with no token. S3 can point at a MinIO endpoint you run. Email sends through the SMTP host you enter. Slack, Teams, calendars, Drive, SharePoint, Jira, Confluence and Notion stay "Not live-tested" until a real account is connected. A green unit test is not a live call.

## Restart

Connector installs, OAuth state, OAuth grants and named secrets are Postgres rows (revision 0028). Restart the API and open the same connector. The install is still there. The secret is still not shown.
