# Tool working-state matrix (platform verification, Layer 1)

Goal: prove every registered tool is in a working state — called for real, not read in the
code. This is Layer 1 of the platform verification plan (set 2026-11-08): make sure the
whole platform and all of its tools work, with accuracy as the priority.

## What it does

`scripts/tool_matrix.py` seeds the demo tenant and invokes **every** tool (built-in and
connector) through the real `ToolPipeline.execute` — the same path the gateway uses, with
entitlement, schema validation, policy, dispatch and audit — using arguments generated from
each tool's own input schema. It classifies each outcome and writes [`report.md`](report.md):

| State | Meaning |
|---|---|
| **working** | returned a real, non-error result |
| **approval-gated** | a write correctly held for approval (healthy) |
| **policy-gated** | policy correctly denied it (healthy) |
| **needs-config** | correctly refused because an install, connection, model or egress list is not set up |
| **needs-referent** | needs a real id (a document, a secret) the harness did not supply; the tool validated correctly |
| **fixture** | returns a canned fixture result |
| **failing** | an unexpected error or crash — the only bucket that is a defect |
| **schema defect** | a `required` field is not defined in `properties`, so the tool is uncallable |

## Run it

```bash
uv run python scripts/tool_matrix.py                 # fixtures, no model
AR_TOOL_MATRIX_LIVE=1 ... uv run python scripts/tool_matrix.py   # with a real model
```

It never prints secrets.

## First run (2026-11-08) — what it found

182 tools. One real defect class and one known fixture:

- **5 connector tools were uncallable** — `email_send`, `email_read`, `s3_get`, `s3_put`,
  `aws_describe_instance` declared `required` fields (`to`/`subject`/`body`, `id`,
  `key`/`text`, `instance_id`) that were never defined in `properties`. A model could not
  see them and schema validation rejected every call. **Fixed** in the connector catalogue
  (`tool_records` now emits every required field as a property), and the
  `scripts/check_tool_descriptions.py` CI lint now fails on any `required` field missing
  from `properties`, so it cannot return.
- `control.checkpoint` returns a fixture result (a known fixture slated for removal, review
  item A14).

Everything else was working, correctly gated (approval/policy/needs-config), or needs a
real referent to exercise. The next layers are the accuracy gym (live, scored) and a single
empty-DB → real-model → all-features platform proof.
