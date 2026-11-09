# Platform certification — tools and accuracy

Date: **2026-11-09**. Model for the live steps: `Qwen/Qwen3-32B` through DeepInfra
(`https://api.deepinfra.com/v1/openai`). The provider key was read from `AR_CERT_LLM_API_KEY`
at runtime; this file does not contain it and no step prints it.

This certifies the effort the owner asked for on 2026-11-08: *make sure the entire platform
works and every tool is in a working state, accuracy first.* It ties together the five
verification layers plus the connector follow-on, states what each proves and does **not**
prove, and records the standing CI regression guard that keeps the tool surface honest.

Deployment, scaling and Docker-production work (M40-T03, Kubernetes/gVisor) was explicitly set
aside for this effort and is **not** in scope here.

## What was built and what it proves

| Layer | Script | Proves | Does not prove |
|---|---|---|---|
| **L1** working-state matrix | `scripts/tool_matrix.py` | every registered tool is invokable through the real `ToolPipeline.execute` — entitlement, schema validation, policy, dispatch, audit — and classifies the outcome | that a gated tool does real work once configured (that is a live, credential-bearing run) |
| **L2** accuracy gym | `scripts/m33c_eval_gym.py` | given an un-named goal, the real agent loop picks the right tool(s) with the right arguments and grounds its answer | behaviour of any model other than the one scored |
| **L3** platform proof | `scripts/platform_proof.py` | builder → chat+tool → knowledge RAG → memory work **together** end to end with a real model | the full running stack (this is in-process on the demo store) |
| **connectors** | `scripts/connector_matrix.py` | each connector installs and every tool dispatches a well-formed request and parses the reply once an account is connected | a live call to a real provider account |

## Results

### L1 — tool working-state matrix (offline, no model)

182 tools. **0 failing, 0 schema defects.**

| state | count | meaning |
|---|---|---|
| working | 28 | ran and returned a real result |
| approval-gated | 30 | a write correctly held for approval |
| policy-gated | 1 | correctly denied by policy |
| needs-config | 89 | correctly refused until installed/connected (incl. 18 uninstalled connectors) |
| needs-referent | 33 | validated fine, needs a real id |
| fixture | 1 | `control.checkpoint`, a dev-only fixture that errors by design (review A14) |
| **failing** | **0** | a genuine, unexpected error |

The first run found and **fixed 5 uncallable tools** — `email_send`, `email_read`, `s3_get`,
`s3_put`, `aws_describe_instance` declared `required` fields that were absent from
`properties`, so a model could never supply them. The fix (`connectors/catalog.py`
`tool_records` now emits every required field as a property) is guarded going forward by
`scripts/check_tool_descriptions.py` (required ⊆ properties). Full table:
[`tool-matrix/report.md`](tool-matrix/report.md), method: [`tool-matrix/README.md`](tool-matrix/README.md).

### connectors — dispatch matrix (offline, no model, no network)

92 connector tools across 21 connectors. **0 genuine failures.**

| state | count | meaning |
|---|---|---|
| dispatched | 6 | reached the stand-in and parsed the reply — full install → auth → request → parse (all AWS: static-key auth + a resolvable host) |
| needs-oauth | 25 | correctly gated: an OAuth **user** token a stub cannot mint |
| needs-egress | 55 | correctly gated: the host does not resolve in the offline harness |
| needs-param | 6 | a required argument the harness did not supply |
| **failing** | **0** | a crash, malformed request or parse error |

Detail: [`connector-matrix/README.md`](connector-matrix/README.md) and its generated `report.md`.

### L2 / B / C — accuracy (live, Qwen3-32B)

Three passes over `docs/testing/eval-gym/accuracy.yaml`, scored against the real model:

| pass | PR | score | finding |
|---|---|---|---|
| L2 first run | #139 | 5/8 | single-tool selection 5/5; chaining 0/3 |
| B chaining fix | #141 | 7/8 | root cause was the gym agent's **setup**, not the model — the chain target tool was unbound; binding the whole file toolset then regressed selection, so bind only what the tasks need |
| C breadth | #142 | 11/12 (92%) | one miss: `write_file` chosen over the specific `export_table` (general-over-specific) |

**Stable finding across all three passes:** single-tool selection from an un-named goal is
~100%; the misses are the model either narrating a plan without calling a tool (variance) or
substituting a general tool for a specific one. Both are model-adherence residuals, not
platform defects — the guidance in `prompts/text/tool_use.md` already says to prefer the
specific tool and not to work values out unaided. Write-up: [`eval-gym/README.md`](eval-gym/README.md).

Live scorecards (`accuracy-scorecard.md`, `live-scorecard.md`) are gitignored by design
(they carry per-run model output); the findings above are the committed record.

### L3 — platform proof (live, Qwen3-32B): **4/4**

1. builder drafts a valid agent definition from one sentence;
2. that agent runs `general.code` to compute a product it cannot do unaided (forces the tool);
3. knowledge RAG cites a planted token;
4. a memory fact is stored and read back.

Method and gotchas: [`platform-proof.md`](platform-proof.md).

## Standing regression guard (CI)

A new offline CI job, **`tool-matrices`**, runs both matrices in `--check` mode on every PR:

```yaml
- run: uv run python scripts/tool_matrix.py --check        # fails on any failing tool or schema defect
- run: uv run python scripts/connector_matrix.py --check   # fails on any failing connector tool
```

`--check` exits non-zero if any tool crashes, errors unexpectedly, or has a `required` field
absent from `properties`. The one documented dev fixture (`control.checkpoint`) is allow-listed
in `scripts/tool_matrix.py` (`_KNOWN_FIXTURES`) so the guard trips on a **new** failure, never
on the known one. Neither script needs a model, a network account or a running stack, so the
job is fast and deterministic.

## Reproduce

```bash
# L1 + connectors — offline, no model, no network:
uv run python scripts/tool_matrix.py            # writes docs/testing/tool-matrix/report.md
uv run python scripts/connector_matrix.py       # writes docs/testing/connector-matrix/report.md
uv run python scripts/tool_matrix.py --check     # exit 1 on any genuine failure / schema defect
uv run python scripts/connector_matrix.py --check

# L2 / B / C + L3 — live, needs the cert key (never printed) from a fully-synced worktree:
AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY="$(cat .secrets/deepinfra_api_key)" \
  uv run python scripts/m33c_eval_gym.py --live --tasks docs/testing/eval-gym/accuracy.yaml
AR_CERT_LLM_API_KEY="$(cat .secrets/deepinfra_api_key)" \
  uv run python scripts/platform_proof.py
```

## Scope and honest limits

- The two matrices are **regression guards**, not live proof. A connector that broke would show
  as `failing`; it is 0 today. A full live call to a provider needs a **real account** (a real
  OAuth token and a reachable host), which no stub can stand in for — this is exactly why the
  review lists 18 connectors as "never called live".
- The accuracy figures are for **one model** (Qwen3-32B). Selection is sensitive to the bound
  tool set: a broad, overlapping set degrades selection, so an agent should bind what its tasks
  need, not everything. The residuals (narrate-without-acting; general-over-specific) are
  model-adherence, to be re-measured per model.
- L3 runs in-process on the demo store with a real model, not against the full deployed stack;
  the running-stack certification is the separate milestone cert reports (e.g.
  [`m31-certification.md`](m31-certification.md)).
