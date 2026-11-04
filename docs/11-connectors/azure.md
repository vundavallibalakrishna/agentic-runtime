# Azure

Read resources, resource groups, virtual machine state and role assignments.

**Category:** Cloud
**Auth:** oauth_client_credentials, bearer
**Verification:** Not live-tested
**Note:** Not live-tested. The client-credentials form matches Microsoft's published example. No subscription was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow

## Setup

1. Register an app in Microsoft Entra. Create a client secret. The token steps are the provider page.
2. On the subscription, assign the Reader role to the app. Role assignment reads also need Reader, or a custom role with Microsoft.Authorization/roleAssignments/read.
3. Client id is the application id. The secret is the client secret. Set Tenant id and Subscription id.
4. The token request is client credentials with scope https://management.azure.com/.default. The token is cached and refreshed.
5. A bearer token you minted yourself can be pasted instead. These tools only call the Azure Resource Manager read APIs.

## Scopes

- `https://management.azure.com/.default`

## Settings

- Tenant id (`tenantId`)
- Subscription id (`subscriptionId`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `azure_list_resources` | List resources | R0 | List resources in the subscription. |
| `azure_list_resource_groups` | List resource groups | R0 | List resource groups. |
| `azure_vm_state` | Read virtual machine state | R0 | Read a virtual machine's instance view. |
| `azure_list_role_assignments` | List role assignments | R0 | List role assignments on the subscription. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
