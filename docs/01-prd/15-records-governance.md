# PRD 15 — Records and assurance

Generic records for any regulated buyer. Industry workflows live in packs. Spec: [spec 21](../03-specs/21-records-governance.md). Plan: M14, plus the tasks named on each story.

### US-REC-01 · Keep an immutable record (P0)
As an **auditor**, I want collected bytes hashed, signed and locked.
- Capture writes the object, the manifest and a custody event in one workflow. Verification is an explicit call.
- Spec: spec 21 §1. Plan: M14-T08.

### US-REC-02 · Hold records for a matter (P0)
As a **tenant admin**, I want a legal hold that two people create and two people release.
- Sweep and erasure skip held rows. Release restores the previous retention class when no other hold covers the row.
- Spec: spec 21 §2. Plan: M14-T09.

### US-REC-03 · Retain and dispose with a certificate (P0)
As a **tenant admin**, I want a schedule per record class and a certificate when something is disposed.
- Evidence, run records, sign-offs and audit archives cannot be kept for fewer than 180 days.
- Spec: spec 21 §2. Plan: M14-T09.

### US-REC-04 · Register our own agents (P0)
As a **tenant admin**, I want one card per published agent version, with oversight counts and an incident log.
- External systems are not rows in this register.
- Spec: spec 21 §3. Plan: M14-T10.

### US-REC-05 · Invite an external participant (P0)
As a **tenant admin**, I want to invite someone who is not an employee, for a limited time, to specific records.
- They use a magic link and TOTP. They cannot chat or call tools. Downloads of PDF and images are watermarked.
- Spec: spec 21 §4. Plan: M14-T11.

### US-REC-06 · Export a binder (P0)
As an **auditor**, I want a ZIP I can verify offline.
- The ZIP has a manifest, an index, the records and a standard-library verifier. A scheduled delivery can wait for sign-off.
- Spec: spec 21 §5 and §10. Plan: M14-T12.

### US-REC-07 · Install a solution pack (P0)
As a **tenant admin**, I want to enable a signed pack without a core upgrade.
- Install, upgrade and uninstall follow the content-pack rules. Disabling the pack hides its navigation and keeps its data.
- Spec: spec 05 §10, spec 21 §6. Plan: M3-T09, M14-T13.
