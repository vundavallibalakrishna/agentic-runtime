# M30 — remove the retired pack

Depends on M29. The product is a generic agentic platform. The industry pack that M16–M19 added, and that M21 parked, is deleted.

### M30-T01 Delete the pack

- **Depends on:** M29-T04
- **Spec:** [m30 checklist](../testing/m30-checklist.md)
- **Do:** Delete the pack package, its routes, screens, catalogues, flag and docs. Add core revision `0031`, which drops the pack schema and version table when they exist and does nothing when they do not. Keep documents, knowledge, connectors, orchestration and the external API.
- **Done when:** `make migrate` succeeds on an empty database and on a database that already has the pack schema. No navigation entry or setting names the pack. Old `/grc` links show a not-found page.
- **Tests:** `libs/ar_domain/tests/integration/test_migrations.py` covers the drop. Playwright still expects `/grc` to show “Page not found”.
