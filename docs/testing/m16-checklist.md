# M16 visual checklist

Sign in as the dev admin. The GRC pack is installed for the dev tenant with `AR_PACK_SIGNATURE_REQUIRED` left false. Open Frameworks, import an OSCAL catalogue, open a control, and look at evidence links.

Seed data is the dev tenant. The admin is `admin@dev.local`. NIST CSF 2.0, NIST SP 800-53, CSA CCM, and id-and-title skeletons for ISO 27001, SOC 2 and PCI DSS are already loaded. Common controls `CC-*` are linked to NIST where the relationship is explicit and left suggested for ISO, SOC 2 and PCI. `fake-llm` answers chat. No model API key.

## Start

```bash
make bootstrap
make migrate
uv run alembic -c packs/grc/alembic.ini upgrade head
make seed
make dev
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login`.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it.

The pack schema is separate from core. `make migrate` stays the core history. The second Alembic command creates schema `grc`.

Earlier screens stay on Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage, Quotas, Evaluations, Platform health and Assurance.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Expect a **GRC** item in the sidebar. Open it. Expect the heading **GRC** and NIST CSF 2.0 in the framework list.
3. ISO 27001 shows the note that the row is ids and titles until a licensed import.
4. Choose **Import OSCAL** and upload a catalogue JSON file. Expect "Catalogue imported." and the new framework in the list.
5. Open **Controls**. Search `access`. Expect common and framework controls. Open one. Expect its title and statement, or the skeleton note when the statement is empty.
6. Open **Evidence**. With no links, expect "No evidence is linked to a control yet."
7. A direct visit to `/grc` while the pack is disabled shows the not-found page. The sidebar item is absent.
8. Narrow to 375px and switch to dark. Frameworks, controls and evidence stay on the same tokens.

## Deferred

Questionnaires, vendors, policies, risk, incidents and the auditor portal are M17–M19. Their tables exist. Their write tools are not registered. HTTP GRC rows stay on the process store (OQ-49). The shipped NIST and CSA files are the public starter set; import a full OSCAL catalogue for the rest. ISO, PCI and SOC 2 statements stay empty until `import-licensed-text` with `attestation: true`.
