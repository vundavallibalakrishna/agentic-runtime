# M33a checklist

Date: 2026-11-05. No model key was required. `AR_SEARCH_API_KEY` was absent in this environment. No search provider was called.

## Seed and segregation of duties

`make seed` inserts, once:

- Local group `approvers`, member `approver@dev.local`.
- Active policy `Seeded write approval`, priority 1000, matching risk class `W2`.
- Approver mode `users`. The user list is the approver, then `admin@dev.local`.
- `four_eyes` is false. The owner is eligible, then the agent-owner invariant returns `sod_violation` (HTTP 422). The approver can decide.
- No conflicting-role rows in `sod_constraints`.

A tenant with no active rule still uses requester mode. In that mode the owner is the only eligible approver and is blocked, so the approval stays `pending`. That is the deadlock this seed removes. A later policy with a lower priority number replaces these approvers.

Re-running `make seed` does not insert a second policy or a second group member.

| Check | Result | Evidence |
|---|---|---|
| Requester mode deadlocks | Pass | Unit: owner HTTP 422 `sod_violation`, approver forbidden, status stays `pending` |
| Seeded users mode | Pass | Unit: member forbidden, owner HTTP 422, approver sets `approved`, the POST then returns HTTP 200 |
| SQL seed is idempotent | Pass | `test_seed_is_idempotent` on a migrated database: one active policy, mode `users`, one `approvers` group, one member, after `apply` twice |
| Browser wipe and seed | `not_live` | No fresh database was opened in a browser for this pass |

## general.fetch

Allowlist denials still return `egress_denied` and do not open a connection. Transient failures retry up to 3 times, waiting 0.25s then 0.75s (tests replace the wait). A timeout or a final 408, 429, 500, 502, 503, or 504 says which host failed and how many attempts ran. The exception text is not copied into the tool result. A normal 200, including after a 503, is unchanged. HTTP methods other than fetch are not retried.

| Check | Result | Evidence |
|---|---|---|
| Connect error, then HTTP 503, then 200 | Pass | Unit: 3 sends, recorded waits 0.25 and 0.75, title `Notes` |
| Allowlist miss | Pass | Unit: `egress_denied`, zero sends |
| Timeout copy | Pass | Unit: `example.com timed out`, `attempts` 3, the transport detail `slow` is absent |
| Live page such as gnu.org | `not_live` | Not fetched in this pass. M31 saw one `upstream_error` on that host |

## general.search

The provider is `brave` or `tavily` from tenant `search.provider`, otherwise `AR_SEARCH_PROVIDER`. The key is the named secret (`search.secretName` or `search.secret_name`), otherwise `AR_SEARCH_API_KEY`. A tenant secret wins over the environment. The key is a request header (Brave) or a request field (Tavily) and is stripped from titles, URLs, and snippets. A 401 or 403 is `search_rejected` and does not repeat the key or the provider body. With no key the tool returns `search_unconfigured`, says `not_live`, and does not call the network.

Do not commit a key. CI leaves `AR_SEARCH_API_KEY` empty.

| Check | Result | Evidence |
|---|---|---|
| `secretName` selects Brave and hides the key | Pass | Unit: header is the secret, result contains `[redacted]`, not the secret or the env key |
| Missing secret falls through to the env key | Pass | Unit: Tavily body uses the env key; HTTP 401 becomes `search_rejected` with no key in the text |
| No key | Pass | Unit: `search_unconfigured`, provider function not called |
| Live Brave or Tavily | `not_live` | `test_live_search_skips_until_a_provider_key_is_set` skips until both variables are set. They were absent here |

## What was not run

Office document create, OCR, and the eval gym are out of this change. No production UI walkthrough was recorded.
