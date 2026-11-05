# M37 — Browser as a tool

A controlled browser for sites that have no connector. The session is the M6 computer's browser, not a second sandbox stack. Pages, cookies and approvals stay inside that session.

This milestone does not change analytics, Temporal durability, or the connector catalog.

## M37-T01 Controlled browser session

**Spec:** [12-sandbox-manager](../03-specs/12-sandbox-manager.md), [mcp-integration](../05-contracts/mcp-integration.md), [OQ-37](../open-questions.md), [OQ-87](../open-questions.md).

**Do:**

- Keep `browser.navigate`, `browser.snapshot`, `browser.click`, `browser.type`, `browser.press`, `browser.scroll`, `browser.screenshot` and `browser.submit_form` on `builtin://browser`.
- Open allowlisted hosts immediately. Treat any other public host as W2 at call time, the same elevation as a non-GET `general.http`. Private and metadata addresses stay denied.
- Keep the cookie jar on the sandbox context. A run id selects that run's context. Another run, conversation or tenant does not receive the cookies.
- Exercise the tools against a local fixture page. A Chromium binary, when present, is a canary. When it is absent the result is `not_live`.

**Done when:** the fixture case passes without a third-party site, off-list navigation waits for approval, and the checklist says what CI did not run.

**Tests:** `libs/ar_domain/tests/unit/test_m37_browser.py`. Checklist: [m37-checklist](../testing/m37-checklist.md).

## Out of scope

DuckDB, Temporal workflow refactors, connector catalog edits, and baking Chromium into `images/sandbox/Dockerfile`.
