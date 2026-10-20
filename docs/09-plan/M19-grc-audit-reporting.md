# M19 — Audit, access reviews and reporting

Goal: auditors, access reviewers and boards work from the pack without a second product.

Exit criteria: an auditor guest completes a PBC request from a watermarked binder; an access-review campaign records decisions; the five report templates render through the core binder API; the signed pack upgrades on a tenant that already has data.

CSCRF ATR and sampling are included before the FY 2026-27 audit cycle (mid-2027).

---

### M19-T01 · PBC tracker and auditor portal
- **Depends on:** M14-T11, M14-T12, M16-T04, M5-T08
- **Areas:** `packs/grc/src/ar_pack_grc/pbc.py`, `apps/web/src/app/guest/portal/**`, template `pbc-responder`
- **Spec:** [api](../10-grc-pack/api.md), [spec 21 §4](../03-specs/21-records-governance.md#4-guest-principals)
- **Do:** PBC endpoints and `:import`. Guest portal `auditor`. A guest sees only requests whose ids are in `pack_record_ids`. Status `provided` requires a core sign-off on the response. Downloads use the core watermark.
- **Done when:** a guest cannot open a request outside the grant; a member with `grc.audit_portal:manage` can.
- **Tests:** grant filter; watermark on the response PDF; import of an XLSX fixture.

### M19-T02 · Access reviews and business SoD
- **Depends on:** M17-T03, M5-T09
- **Areas:** `packs/grc/src/ar_pack_grc/{entitlements.py,sod_rules.py}`, template `access-review-coordinator`
- **Spec:** [api](../10-grc-pack/api.md), [domain-model](../10-grc-pack/domain-model.md)
- **Do:** Ingest entitlements from the IdP connectors into `grc.entitlements`. Business rules in `grc.sod_rules`. Campaign kind `access_review` uses core sign-off for each item. These rules do not write core `sod_constraints`.
- **Done when:** a pair that matches a business rule is flagged on the campaign item; platform SoD behaviour is unchanged.
- **Tests:** ingest idempotency; conflict detection; no write to `sod_constraints`.

### M19-T03 · Attestations
- **Depends on:** M16-T01, M5-T08
- **Areas:** `packs/grc/src/ar_pack_grc/campaigns.py`
- **Spec:** [api](../10-grc-pack/api.md)
- **Do:** Campaign kinds `attestation` and `acknowledgement`. `:start` materialises items and audits `grc.campaign.started`. A decision writes a core sign-off bound to the statement hash and audits `grc.campaign_item.decided`. Acknowledgement also audits `grc.policy.acknowledged`. `:close` with open required items returns 409 unless `force: true` with step-up.
- **Done when:** the stored sign-off hash equals the statement the assignee saw.
- **Tests:** statement hash; force-close step-up; reminder routine `grc-campaign-reminder`.

### M19-T04 · Report templates
- **Depends on:** M14-T12, M16-T06
- **Areas:** `packs/grc/src/ar_pack_grc/reports.py`, template `board-reporter`, skill `cscrf-atr`, routine `grc-board-pack`
- **Spec:** [api](../10-grc-pack/api.md), [agent-templates](../10-grc-pack/agent-templates.md)
- **Do:** Templates `soa`, `soc2_binder`, `cscrf`, `dpdp_breach`, `board_pack`. `POST /api/v1/ext/grc/reports:render` calls the core binder API and audits `grc.report.exported`. `cscrf` uses skill `cscrf-atr` and the sampling skill from M18-T05. `board_pack` delivery sets `reviewBeforeSend`. The SoA lists control ids; it does not embed licensed statement text the tenant has not imported.
- **Done when:** each template returns a binder id; the offline verifier accepts the ZIP; a board pack is not delivered before sign-off.
- **Tests:** one render fixture per template; review-before-send; licensed-text absence.

### M19-T05 · Pack release, signing and upgrade
- **Depends on:** M19-T01, M19-T02, M19-T03, M19-T04, M16-T07, M18-T07, M18-T08, M19-T06, M19-T07, M19-T08, M3-T09
- **Areas:** `packs/grc/pack.yaml`, `packs/grc/tests/test_upgrade.py`
- **Spec:** [spec 05 §10](../03-specs/05-agent-registry.md#10-content-packs), [definition-schema §11.2](../05-contracts/definition-schema.md#112-content-pack-kind-contentpack), [OQ-28](../open-questions.md)
- **Do:** Content-pack manifest for `grc` listing resources, extension schema `grc`, mount `/api/v1/ext/grc`, nav `/grc`, the permissions in [authn-authz §9](../06-security/authn-authz.md#9-permissions-added-after-the-m1-baseline) and the `grc.*` audit actions. Sign the manifest with a key in `AR_PACK_TRUSTED_KEYS`. Upgrade test: install 1.0.0, write a control, upgrade to the next version, assert the control remains and `grc_alembic_version` moves. Core Alembic head is unchanged.
- **Done when:** upgrade keeps tenant rows; a bad signature is rejected when `AR_PACK_SIGNATURE_REQUIRED` is true; uninstall without `dropSchema` keeps schema `grc`.
- **Tests:** signed install; upgrade; uninstall keeps data; core `alembic heads` still one head.

### M19-T06 · Regulator inspection room
- **Depends on:** M19-T01
- **Areas:** `packs/grc/src/ar_pack_grc/inspections.py`
- **Spec:** [use-cases U23](../10-grc-pack/use-cases.md)
- **Do:** `grc.inspections`. Creating an inspection builds a core binder and a guest grant whose scope is that binder only. The guest is `kind=external`.
- **Done when:** the guest cannot open a second binder.
- **Tests:** grant scope; audit `grc.inspection.opened`.

### M19-T07 · DSAR and consent records
- **Depends on:** M14-T09, M16-T01
- **Areas:** `packs/grc/src/ar_pack_grc/privacy.py`
- **Spec:** [use-cases U28–U29](../10-grc-pack/use-cases.md), [spec 17](../03-specs/17-audit-usage-metering.md)
- **Do:** `grc.dsar_requests` and `grc.consent_records`. A DSAR `erasure` for a platform user starts the core erasure workflow after sign-off and skips held records. Consent state changes require an evidence item.
- **Done when:** erasure does not delete a held evidence item; a consent row without evidence returns 422.
- **Tests:** hold skip; consent evidence required.

### M19-T08 · Resilience tests and model inventory
- **Depends on:** M16-T02, M14-T10
- **Areas:** `packs/grc/src/ar_pack_grc/resilience.py`
- **Spec:** [use-cases U25–U26](../10-grc-pack/use-cases.md)
- **Do:** `grc.resilience_tests` for BCP and DR. Model-risk entries are `grc.assets` with `kind=model`, an owner, a tier, and links to evidence. When the model is an agent on this platform, the row also stores the core `agent_card` id. No model-training workflow.
- **Done when:** a resilience fail requires an evidence item; a model asset is not written into `agent_cards`.
- **Tests:** kind check; card id optional.
