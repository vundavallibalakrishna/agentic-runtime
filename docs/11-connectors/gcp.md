# Google Cloud

Read projects, compute instances, storage buckets and IAM policies.

**Category:** Cloud
**Auth:** api_key
**Verification:** Not live-tested
**Note:** Not live-tested. The JWT matches Google's service-account example and is checked with the public key. No project was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://cloud.google.com/iam/docs/keys-create-delete

## Setup

1. In Google Cloud IAM, create a service account. Grant it roles/viewer, or roles/browser plus the read roles for Compute, Storage and Resource Manager. The key guide is the provider page.
2. Create a JSON key and paste the whole file as the secret. The private key is not sent to the model.
3. The connector builds the JWT Google documents (iss, scope, aud, iat, exp) and exchanges it at https://oauth2.googleapis.com/token. The bearer is cached and refreshed.
4. Scope is https://www.googleapis.com/auth/cloud-platform.read-only. These tools do not create or change cloud resources.
5. Set Project id. Zone defaults to us-central1-a for the instance list.

## Scopes

- `https://www.googleapis.com/auth/cloud-platform.read-only`

## Settings

- Project id (`projectId`)
- Zone (`zone`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `gcp_list_projects` | List projects | R0 | List projects the service account can see. |
| `gcp_list_instances` | List compute instances | R0 | List compute instances in a zone. |
| `gcp_list_buckets` | List storage buckets | R0 | List storage buckets in a project. |
| `gcp_get_iam_policy` | Read an IAM policy | R0 | Read a project's IAM policy. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
