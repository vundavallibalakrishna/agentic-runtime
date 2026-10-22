# M3 visual checklist

Start from a fresh checkout. M2.5 still applies: [m2.5-checklist](m2.5-checklist.md).

```bash
make bootstrap
make dev AUTO_PORTS=1
```

`make seed` writes the dev tenant, the four users, fake-llm, and the published agents `assistant`, `helpdesk` and `builder` into Postgres. The dev API serves the same catalogue from memory ([OQ-31](../open-questions.md), [OQ-34](../open-questions.md)). Sign in with **Sign in as admin@dev.local**. No model API key is required.

Screenshots for light and dark, desktop (1280) and mobile (375), live under `docs/testing/m3/`.

## 1. Catalogue

1. Open **Agents**. The page lists Assistant, Builder and Helpdesk. Each card shows a short description, the greeting, the owner and the published version.
2. Search for `help`. Only Helpdesk remains. Clear the search.
3. Filter status to **Draft**. The published sample agents disappear and the empty line is shown. Set the filter back to any status.
4. Choose **Favourite** on Helpdesk. The button changes to **Remove favourite**.
5. Choose **Chat** on Helpdesk. Chat opens on a new conversation with that agent.

## 2. Describe an agent

1. Open **New agent** (also linked from Home).
2. The page leads with **What should this agent do?** Templates sit below that field.
3. Type `create an agent that reviews vendor SOC 2 reports and flags gaps` and choose **Draft**.
4. The preview shows a persona, the instructions, a **files** tool slot, and a validation panel. The tool is a warning, not a blocking error.
5. Type `Ask for the report name first.` and choose **Update draft**. The preview instructions include that sentence.
6. Choose **Use this draft**. The editor opens with those instructions. The agent is still a draft.

## 3. Template, test, publish, roll back

1. Open **New agent** and choose **Support**.
2. Replace the instructions with a shorter sentence. Choose **Advanced**, then the **YAML** tab. The text contains the same sentence.
3. Under **Test chat**, send `hello from the draft`. The reply includes `fake:`.
4. Enter the change note `first release` and choose **Publish**. Version history shows `v1 published`.
5. Change the instructions again, note `second release`, and publish. History shows `v2 published`.
6. Choose **Roll back** on v1. A newer published version appears.
7. Choose **Export bundle**. The YAML includes `kind`. Paste it into **Import bundle** and choose **Preview import**. The result names an action (`unchanged`, `new_version` or `create`) and does not publish a second copy on its own.

## 4. States

1. On Agents, a failed load shows the error line. An empty filter shows the empty line. The first load shows "Loading agents".
2. Light and dark both use the existing tokens. At 375 px the catalogue stacks and the builder field stays usable.
