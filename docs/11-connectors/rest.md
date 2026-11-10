# REST API

Call a REST API the tenant names.

**Implementation:** Built
**Category:** Developer
**Auth:** bearer, api_key, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Checked against a recorded HTTP example. No customer API was called.
**Local rate limit:** 60 calls a minute.

## Setup

1. Set the API base URL.
2. Store a bearer token or an API key. It is not shown again.
3. A POST asks for approval.

## Scopes

- `api`

## Settings

- Base URL

## Tools

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `rest_get` | GET a path | R0 | GET a path on the connected API. |
| `rest_post` | POST a path | W2 | POST a path on the connected API. |

Proof label: `unit`. A live call belongs in `scripts/certify_live.sh`.
