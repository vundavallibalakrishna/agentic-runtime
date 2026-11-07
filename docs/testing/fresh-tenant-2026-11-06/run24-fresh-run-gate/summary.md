# Fresh-run — 2026-11-07T07:05:29.802Z

Tenant admin: ada@acme.example. Web: http://localhost:3000.

**4 passed, 0 failed, 3 skipped.**

| Step | Result | Detail |
|---|---|---|
| sign-in | pass | signed in as ada@acme.example |
| configure-models | skip | the tenant already has its models configured |
| chat-answers | pass | the assistant answered a plain question |
| knowledge-search | pass | a collection was indexed and searched by meaning |
| knowledge-in-chat | skip | the default assistant did not search the library (tool choice, F66/M39) |
| memory-recall | pass | a fact saved on the Memory screen was recalled in chat (amber lantern → sienna) |
| second-user | skip | AR_FRESH_SECOND_EMAIL is not set |
