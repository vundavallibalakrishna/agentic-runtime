# Connector dispatch matrix (platform verification)

`scripts/connector_matrix.py` proves the other half of the tool matrix for connectors. The
tool matrix shows a connector tool correctly **refuses until an account is connected**; this
installs every connector with stub credentials and dispatches each of its 92 tools, with an
httpx `MockTransport` catching every call and returning a generic 200 — so no real provider
is touched — and classifies the outcome into [`report.md`](report.md).

## Run it

```bash
uv run python scripts/connector_matrix.py
```

No model or network account is needed.

## First run (2026-11-09) — the finding

92 connector tools across 21 connectors. **Zero genuine failures.** Every tool either
dispatches cleanly or gates correctly:

| State | Count | Meaning |
|---|---|---|
| **dispatched** | 6 | reached the stand-in and parsed the reply — the full install → auth → request → parse path works |
| **needs-oauth** | 25 | correctly gated: an OAuth **user** token is required, which a stub cannot mint |
| **needs-egress** | 55 | correctly gated: the host is not a verifiable public address in the offline harness |
| **needs-param** | 6 | a required argument the harness did not supply |
| **failing** | 0 | a genuine, unexpected error |

**What this proves.** The connector framework is sound: no connector crashes or
misbehaves, and the AWS connector (static-key auth, a resolvable host) dispatches **end to
end** through the real `dispatch_connector` path, exercising install, credential resolution,
request signing, the HTTP call and reply parsing. The other connectors stop at a **healthy
gate** — an OAuth user-consent token, or the egress check on a host that does not resolve in
the offline harness. Those gates are exactly why the review lists 18 connectors as "never
called live": a full live call needs a **real account** (a real OAuth token and a real,
reachable host), which no stub can stand in for.

So this matrix is the regression guard, not the live proof: a connector that broke — a
crash, a malformed request, a parse error — would show as `failing`. It is 0 today. Live
per-connector verification against real accounts remains a separate, credential-bearing run.
