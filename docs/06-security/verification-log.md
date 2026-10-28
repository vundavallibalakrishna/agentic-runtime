# Security verification log

Recorded by M14-T07. Each threat-model row has a test that is part of the suite.

| Threat | Result | Test |
|---|---|---|
| T1 | pass | `libs/ar_domain/tests/integration/test_rls.py`, cross-tenant 404 in `services/api/tests/unit/test_m14_api.py` |
| T3 | pass | `evals/redteam/injection.yaml` via the eval runner; `test_m14_records.py` recognisers |
| T4 | pass | `apps/web/src/lib/markdown-exfil.test.ts`, `ar_common.markdown_exfil` |
| T9 | pass | existing secret scrubbing tests; evidence provenance stores hashes only |
| T10 | pass | header snapshot in `test_m14_api.py`; SSRF cases in `libs/ar_common/tests/unit/test_core.py` |
| T12 | pass | `verify_chain` in `test_m14_records.py`; audit append-only trigger from M1 |
| T16 | pass | metadata support grant receives 404 on file content |
| T17 | pass | erasure skips held conversations in `test_m14_records.py` |
| T-EV1 | pass | evidence verify recomputes SHA-256 and the Ed25519 manifest |
| T-EV2 | pass | guest chat route returns 403 `guest_forbidden` |
| T-EV4 | pass | watermark failure raises and does not return the original bytes |

Accepted risks: none. A full OWASP ZAP container baseline remains on the nightly workflow (OQ-47). gVisor escape probes stay on the nightly kind job named in the threat model.
