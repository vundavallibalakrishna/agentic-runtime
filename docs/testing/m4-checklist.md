# M4 visual checklist

## Run

```bash
make dev
```

In another shell, from `apps/web`:

```bash
pnpm dev
```

`make seed` writes the dev tenant and the tool tables into Postgres. The dev API serves the same catalogue from memory ([OQ-31](../open-questions.md), [OQ-35](../open-questions.md)). Sign in with **Sign in as admin@dev.local**. No model API key is required.

Seeded servers: Files, Conversations, Web, Control, Tickets, Petstore, Warehouse. The published **Desk** agent can file a ticket and count orders. The tickets account is already connected for the dev admin. `security.allow_self_review` is on for this tenant so one admin can approve a server.

## Click-through

1. Open **Tools**. The page lists the seeded servers with a status. Loading shows a skeleton. A failed load shows the error and **Try again**.
2. Simple mode is the default. **Advanced** reveals the kind selector (Remote MCP, OpenAPI, SQL). The choice is remembered in this browser.
3. Register an echo server: short name `echo`, address `memory://echo`, **Register**. The page says **Approved** and Echo appears in the list.
4. Open **Connections**. Tickets shows **Connected**. Warehouse is listed under data connections. **Disconnect** removes the grant. **Connect** shows the authorize link.
5. Open **Ask the desk agent**. The agent picker is Desk. Send `File a ticket: the printer on floor 3 is jammed`. The reply contains `TCK-1001` and a tool card for `tickets.create_ticket`.
6. Send `How many orders are in the warehouse?`. The reply is `3`.
7. Return to **Tools**. Recent calls lists both calls with redacted arguments.
8. A second tenant cannot see the echo server (the API returns 404).
9. Creating a pet through Petstore is refused until approvals exist. The call is denied with `policy_denied`.

## Light, dark, and narrow

1. The theme control switches light and dark. Both use the existing tokens.
2. At 375 px the server cards stack, the register form stays usable, and the chat composer remains reachable.

Screenshots from the Playwright run live in this directory: `desktop-light-tools.png`, `desktop-dark-tools.png`, `mobile-light-tools.png`, `mobile-dark-tools.png`, and the same set for `connections` and `desk`.
