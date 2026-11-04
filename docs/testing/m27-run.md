# M27 run guide

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


Sign in with dev sign-in as `admin@dev.local`.

## Catalog

Open Connectors. Search for ServiceNow, Salesforce, Zendesk, HubSpot, Okta, Entra, AWS, Azure or Google Cloud. Filter by Work, Identity or Cloud. Each new card shows Not live-tested. The note under the badge says no customer account was connected.

Open a connector. The page lists the setup steps, a link to the provider's app page, the scopes, and each tool. Writes say "Asks first". AWS, Azure, Entra ID and Google Cloud have no write tools.

Connect and install. The secret field is a password input and the saved page does not show it. Test connection reports success or a message you can act on (401 reconnect, 403 scopes, 404 not found, 429 retry-after). Turn a tool off and it stays off for that install.

On an agent, open Advanced, then the tools section. Connector tools can be attached one by one. A write still waits for approval in chat.

## Honest labels

None of the nine connectors were called on a customer account for this milestone. AWS signatures were checked against Amazon's published S3 examples. Azure and Google token requests were checked against the providers' documented bodies and claims. A green unit test is not a live call. The checklist says when a chat turn used a recorded-response replay.

## Restart

Connector installs, OAuth state, OAuth grants and named secrets stay on the M26 Postgres rows (revision 0028). Cloud access tokens are sealed onto the same service-connection row and are still there after a restart. The secret is still not shown.
