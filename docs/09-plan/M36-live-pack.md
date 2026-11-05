# M36 — Connector live pack

Depends on M27. Connectors that shipped as `not_live` stay built. A canary promotes one to live only after a recorded read. GitHub's public read stays the reference call.

### M36-T01 Live-pack harness and honest labels

- **Depends on:** M27-T04
- **Spec:** [11-connectors](../11-connectors/README.md), [m36 checklist](../testing/m36-checklist.md), [OQ-74](../open-questions.md)
- **Do:** A dry-by-default canary for every catalogue connector. With `AR_M36_LIVE=1` and that connector's env, it reads a channel, issue, file or page. A write runs only when `AR_M36_WRITE=1` and `AR_M36_WRITE_APPROVED=1`. The report and ledger omit tokens. The catalog and the connectors screen say built separately from live, public or not live-tested. Google Calendar and Google Drive accept a pasted bearer. SharePoint's steps say the tools call the signed-in OneDrive. Teams' steps say the read lists channels and does not read message text.
- **Done when:** `make live-pack` and the unit test pass with no provider token. The committed ledger has no rows. GitHub's canary still reads `octocat/Hello-World` `README` and does not demote the live label.
- **Tests:** `libs/ar_domain/tests/unit/test_m36_live_pack.py`
