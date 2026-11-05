# M33a — Seed SoD and fetch/search trust

Depends on M32. This milestone does not add Office create, OCR, or an eval gym.

### M33a-T01 Fresh seed, fetch, and search

- **Depends on:** M32-T01
- **Spec:** [spec 09 §2 and §12](../03-specs/09-policy-approvals.md#2-defaults-by-risk-class-no-rule-matched), [OQ-70](../open-questions.md), [m33a checklist](../testing/m33a-checklist.md)
- **Do:** `make seed` installs an active W2 policy in users mode so the seeded approver can finish a write the agent owner cannot self-approve. `general.fetch` retries transient upstream failures and names the host in the error. `general.search` reads `AR_SEARCH_API_KEY` or the tenant secret (`secretName` or `secret_name`) and does not call a provider when no key is set.
- **Done when:** A fresh seed no longer leaves a W2 HTTP call pending with nobody able to approve it. Fetch retries are covered without weakening the egress allow list. Search tests skip when the key is absent, and the checklist labels that path `not_live`.
- **Tests:** `libs/ar_domain/tests/unit/test_m33a_trust.py`, `libs/ar_domain/tests/integration/test_migrations.py` (`test_seed_is_idempotent`)
