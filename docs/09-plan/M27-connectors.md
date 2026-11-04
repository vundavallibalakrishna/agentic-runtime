# M27 — Connector batch two

Depends on M26. A customer installs ServiceNow, Salesforce, Zendesk, HubSpot, Okta, Microsoft Entra ID, AWS, Azure or Google Cloud, follows that provider's app-registration steps, tests the connection, and attaches the tools to an agent.

The earlier deferral is lifted. A connector that cannot be called without a customer account is still built, and it is labelled not live-tested. The GRC pack stays parked. This milestone does not import it and does not change its migrations.

## M27-T01 Cloud auth and shared limits

**Spec:** [m27-connectors](../06-security/m27-connectors.md), [OQ-63](../open-questions.md).

**Do:**

- Sign AWS requests with Signature Version 4. The secret is an HMAC input, not a header value and not a URL parameter.
- Cache Azure client-credentials tokens and Google service-account bearers on the connection row, and mirror the sealed token in Valkey when a client is configured.
- Count connector calls in Valkey when a client is configured so workers share one bucket. Without Valkey the bucket stays on the process.

**Done when:** the published S3 signature examples match, a second Azure or Google call does not mint again, and two processes share one Valkey bucket.

**Tests:** `libs/ar_domain/tests/unit/test_m27_connectors.py`.

## M27-T02 Nine connectors

**Spec:** [11-connectors](../11-connectors/README.md).

**Do:**

- ServiceNow incidents and changes, plus a table query.
- Salesforce SOQL, get, create, update and describe.
- Zendesk search, read, create and comment.
- HubSpot contacts, companies and deals.
- Okta users, groups, app assignments, and deactivate.
- Microsoft Entra ID users, groups, app registrations and sign-in logs.
- AWS read-only EC2, S3 buckets, IAM and CloudTrail, with an access key or a role.
- Azure Resource Manager reads.
- Google Cloud reads.
- Reads are R0. Writes are W2. Each tool can be turned off. Errors for 401, 403, 404 and 429 say what to do. Lists follow the provider's next page.

**Done when:** each tool returns the shape from a recorded provider example through the stand-in. The stand-in is not a live call.

**Tests:** `test_m27_connectors.py`.

## M27-T03 Catalog and guides

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- The existing catalog lists the nine connectors with the same categories, search, install flow and status badges.
- Each connector has a page under `docs/11-connectors/` with the provider's registration steps and links.

**Done when:** Playwright captures the catalog and each new connector page in light and dark at desktop and mobile widths.

**Tests:** `apps/web/e2e/m27-connectors.spec.ts`.

## M27-T04 Proof

**Spec:** [m27-checklist](../testing/m27-checklist.md).

**Do:**

- Record exactly one of live, provider API or reference server, or not live-tested for each connector.
- Where a connector cannot be reached, prove the tool contract with a recorded-response replay and say that it is a replay.
- Use Qwen/Qwen3-32B for one end-to-end conversation that calls a batch-two tool.

**Done when:** the checklist table matches the badges.

## Out of scope

A third connector batch. Changing GRC pack migrations. Calling a customer tenant for a provider that did not answer.
