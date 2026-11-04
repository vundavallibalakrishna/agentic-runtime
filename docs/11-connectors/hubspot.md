# HubSpot

Search and read contacts and companies, create and update a contact, and list deals.

**Category:** Work
**Auth:** bearer, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Not live-tested. Tools match HubSpot CRM v3 examples. No portal was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://developers.hubspot.com/docs/guides/apps/private-apps/overview

## Setup

1. In HubSpot, open Development, Legacy apps, and create a private app. The guide is the provider page.
2. Scopes: crm.objects.contacts.read, crm.objects.contacts.write, crm.objects.companies.read and crm.objects.deals.read. Leave contacts.write off when the agent should not change contacts.
3. Copy the access token and paste it as a bearer secret. It starts with pat-.
4. A public OAuth app uses https://app.hubspot.com/oauth/authorize and https://api.hubapi.com/oauth/v1/token with the same scopes.
5. Creating or updating a contact asks for approval.

## Scopes

- `crm.objects.contacts.read`
- `crm.objects.contacts.write`
- `crm.objects.companies.read`
- `crm.objects.deals.read`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `hubspot_search_contacts` | Search contacts | R0 | Search contacts. |
| `hubspot_read_contact` | Read a contact | R0 | Read one contact. |
| `hubspot_search_companies` | Search companies | R0 | Search companies. |
| `hubspot_read_company` | Read a company | R0 | Read one company. |
| `hubspot_create_contact` | Create a contact | W2 | Create a contact. |
| `hubspot_update_contact` | Update a contact | W2 | Update a contact. |
| `hubspot_list_deals` | List deals | R0 | List deals. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
