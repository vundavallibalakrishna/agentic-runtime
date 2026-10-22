# M5 visual checklist — policy and approvals

Run the stack, then walk the numbered steps. Screenshots for light and dark, at 1280×800 and 375×812, live in `docs/testing/m5/`.

## Start

```bash
make bootstrap && make dev
```

If a host port is taken, `make ports-check` or `AUTO_PORTS=1 make dev`.

Seeded login: `admin@dev.local` (no model key). The dev tenant already has Tickets, Warehouse, Petstore and the published **Desk** agent. Desk is owned by the builder, so the admin who asks for a write can approve it. One review queue, **Output review**, has a sample item prepared by the builder.

`AR_OPA_URL` stays empty. Decisions use the in-process evaluator, which follows the same rules as `policies/rego/ar`.

## Click-through

1. Open `/login` and choose **Sign in as admin@dev.local**. Chat opens.
2. Earlier milestones still work: Agents, Tools, Connections, and a Desk reply that files a ticket or counts warehouse orders.
3. Open Chat with Desk (`/chat?agent=desk`). Send `Create a pet named Fido`. The reply says it is waiting for approval. The tool card links to the approval.
4. Open **Approvals**. The pet call is under **To decide**, with the tool name, risk `W2`, and a short preview. Empty, loading and error states are the sentence, the skeleton, and the retry line.
5. Approve it. Return to the same conversation. The reply says `Created pet` and the tool ran once.
6. Open the approval again. A second approve is refused. Changing the arguments after approval does not match the stored hash.
7. Open **Policies** (`/admin/policies`). Switch to **Advanced** and save a document that asks for approval on `petstore.delete_pet`, with `approvers.mode` `users` and `approvers.users` set to the seeded approver. Activate it. **Try it** shows a decision without changing the live rules of a draft. A live deny still wins when an allow draft is included in the same simulation.
8. Ask Desk to `Delete pet 1`. The approval is `W3` and four-eyes, so the requester cannot decide it. Sign in as `approver@dev.local`, open the approval, confirm it is you, and approve. Sign back in as `admin@dev.local`. The delete has run.
9. A deny rule blocks a call and the assistant sees the rule message.
10. Open **Reviews** from Approvals. The sample output is waiting. Open it, confirm it is you, and sign. The preparer cannot sign their own item.
11. Simple / Advanced on Approvals and Policies remembers the choice. Advanced shows the document and standing approvals. Light and dark both use the theme tokens. At 375px the inbox stacks; at 1280px the same actions stay on the page.

## What this milestone does not move

Chat state stays in the API process. The model gateway and a Temporal worker are not on the HTTP path. Those cut over in M10, when routines cannot live inside the API process. Audit rows written during the chat are listed by `GET /api/v1/audit-events`.
