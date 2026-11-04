# M27 checklist

Proof date: 2026-11-04. Chat model: Qwen/Qwen3-32B through DeepInfra (`https://api.deepinfra.com/v1/openai`). The provider key was read from `AR_CERT_LLM_API_KEY` and is not in this file. The API listened on `18140` with `AR_DURABLE_STATE=memory`. Postgres on 5432 and the apps on 8000, 8001 and 8013 were not used.

## Per connector

Exactly one label. A stand-in in a unit test is not a live call. A recorded-response replay is not a live call.

| Connector | Label | What was actually called |
|---|---|---|
| ServiceNow | (c) not live-tested | Recorded Table API examples in unit tests. No instance was connected. |
| Salesforce | (c) not live-tested | Recorded REST API v59.0 examples in unit tests. No org was connected. |
| Zendesk | (c) not live-tested | Recorded Support API examples in unit tests. No subdomain was connected. |
| HubSpot | (c) not live-tested | Recorded CRM v3 examples in unit tests. No portal was connected. |
| Okta | (c) not live-tested | Recorded Users API examples in unit tests. No org was connected. |
| Microsoft Entra ID | (c) not live-tested | Recorded Microsoft Graph examples in unit tests. No directory was connected. |
| AWS | (c) not live-tested | Signature Version 4 matches Amazon's published S3 GET and PUT examples. DescribeInstances, ListUsers and AssumeRole were unit-tested against recorded XML. No AWS account was called. |
| Azure | (c) not live-tested | The client-credentials form matches Microsoft's published example. Resource JSON was a recorded example. `login.microsoftonline.com` was not called. |
| Google Cloud | (c) not live-tested | The service-account JWT matches Google's documented claims and verifies with the public key. Project JSON was a recorded example. `oauth2.googleapis.com` was not called. |

## Real model

- [x] Recorded-response replay, not a live ServiceNow call. A local process on `127.0.0.1:18142` returned the recorded incident `INC0009001` (`Cannot reach the mail gateway`). It is not a ServiceNow instance.
- [x] The same replay returned 404 for `missing` (`The provider could not find that item (404).`) and 429 for `limited` (`Retry after 15`).
- [x] Qwen/Qwen3-32B called `connectors.servicenow_get_incident` with `sys_id` `abc`. The run completed. The summary was: The ServiceNow incident number is **INC0009001**.

## Signing that was not verified on the provider

- AWS did not answer `GetCallerIdentity` or a signed read. The published signatures were checked locally.
- Azure AD did not issue a token. The request body was checked locally.
- Google did not issue a token. The JWT claims and signature were checked locally.

## Durability

M26 revision 0028 is unchanged. Installs, OAuth state, grants and named secrets stay on those tables. Cached cloud tokens are sealed columns on `service_connections`, which revision 0025 already stores.

## Screens

Playwright captures the catalog and each batch-two connector page in light and dark at desktop and mobile widths. Walkthrough: `docs/testing/m27/walkthrough.webm`.
