# Salesforce

Run SOQL, read a record, create and update a record, and describe an object.

**Implementation:** Built
**Category:** Work
**Auth:** oauth_authorization_code, oauth_client_credentials, bearer
**Verification:** Not live-tested
**Note:** Not live-tested. Tools match Salesforce REST API v59.0 examples. No org was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://help.salesforce.com/s/articleView?id=sf.connected_app_create_api_integration.htm

## Setup

1. In Setup, open App Manager and choose New Connected App. Enable OAuth.
2. Callback URL is this platform's service-connection callback. Selected OAuth scopes are api and refresh_token (Perform requests at any time).
3. Copy the consumer key into Client id and the consumer secret into the secret.
4. Set the site URL to the instance, for example https://your-domain.my.salesforce.com. Calls do not go to login.salesforce.com.
5. A bearer token you already hold can be pasted instead of completing OAuth. It is not shown again.
6. Client credentials need the connected-app flow enabled for that app. Creating or updating a record asks for approval.

## Scopes

- `api`
- `refresh_token`

## Settings

- Instance URL (`baseUrl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `salesforce_query` | SOQL query | R0 | Run a SOQL query. |
| `salesforce_get_record` | Get a record | R0 | Read one record by id. |
| `salesforce_create_record` | Create a record | W2 | Create a record from a JSON fields object. |
| `salesforce_update_record` | Update a record | W2 | Update a record from a JSON fields object. |
| `salesforce_describe` | Describe an object | R0 | Describe an sObject. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
