# Plan: a small install

Status: the owner accepted the recommendations in section 6 on 21 November 2026 (decisions 1 to 3 as recommended; 4 after stage 1's measurements; 5 after Compose). Stage 1 is in progress: the core and the feature files are built, and CI's `compose-smoke` job is where they are proved and measured. Stage 2 is built: `worker` runs the runtime and system workers in one process (`ar_common.work`), so the core is nine containers; `compose.split-workers.yaml` runs them apart.

## 1. Why

The Compose install starts 19 long-running containers (20 with the virus scanner). On 21 November 2026 that install, run on a laptop with 8 GB given to Docker, brought the machine down during certification run 6. The owner's customers run the product in-house, for their own staff, on one machine. Most of them do not need every service, and none of them should need 19 containers to get a working product.

The goal is an install that a basic in-house tenant can run in **9 containers**, with the rest switched on only when the customer uses the feature they serve. A later stage can take it to 6 or 7 if the owner accepts the trade-offs in section 6.

Nothing in the product's behaviour changes. This plan changes what is started, not what the code does, except where a stage says so.

## 2. What runs today

| Group | Containers | Count |
|---|---|---|
| Product services | `api`, `web`, `runtime-worker`, `system-worker`, `ingest-worker`, `model-gateway`, `mcp-gateway`, `mcp-openapi`, `mcp-sql`, `sandbox-manager`, `sandbox-agent`, `channels` | 12 |
| Dependencies | `postgres`, `valkey`, `temporal`, `seaweedfs`, `openbao`, `opa`, `squid` | 7 |
| Optional today | `clamav` (profile `scan`) | 1 |

Measured on 21 November 2026 (run 6, main `a1319771`). Memory was captured for some containers only; the rest were not measured before the stack was stopped.

| Container | Memory | Image |
|---|---|---|
| `clamav` | 984 MiB | 392 MB |
| `ingest-worker` | 204 MiB idle, 939 MiB while parsing | 11.1 GB |
| `api` | 474 MiB | 1.3 GB |
| `system-worker` | 310 MiB | 1.29 GB |
| `temporal` | 157 MiB | 203 MB |
| `seaweedfs` | 137 MiB | 687 MB |
| `postgres` | 90 MiB | 686 MB |
| `openbao` | 41 MiB | 258 MB |
| other Python services | not measured | 0.66 to 1.3 GB each, sharing layers |
| sandbox image (one per running computer) | not measured | 4.5 GB |

Data after one certification pass: 121 MB of database, 7 MB of files.

## 3. What the code allows today

Read from the code at `a1319771` on 21 November 2026. Nothing in this section has been confirmed by a run yet; stage 1 does that.

### Services that can be left out

| Service | Finding | Evidence |
|---|---|---|
| `model-gateway` | Models are called at the provider's own address. The gateway is used only when a provider has no address. In run 6 it received no request at all. | `libs/ar_domain/src/ar_domain/chat/service.py:1955-1974`, `docs/03-specs/04-model-gateway.md:84` |
| `mcp-openapi` | Serves no product route, and no code reads `AR_MCP_OPENAPI_URL`. | `connectors/mcp_openapi/src/ar_mcp_openapi/main.py:17` |
| `mcp-sql` | No code reads `AR_MCP_SQL_URL`. Whether a SQL connection a tenant installs reaches it another way is not confirmed. | `connectors/mcp_sql/src/ar_mcp_sql/main.py:27-57` |
| `channels` | Only Slack, Teams and email use it. Its state is in memory. | `services/channels/src/ar_channels/main.py:34-127` |
| `sandbox-agent` (the standalone container) | A computer is a container the sandbox manager starts from the sandbox image. No caller of this standalone container was found. | `compose.yaml` service `sandbox-agent` |
| `sandbox-manager` | Needed only when agents use a computer. It runs as root with the Docker socket, so it stays its own container and is never merged. Staging and production refuse to start without its address today. | `compose.yaml:395,404`, `libs/ar_domain/src/ar_domain/sandboxes/manager_launch.py:145-150` |

### Dependencies that can be left out

| Dependency | Finding | Evidence |
|---|---|---|
| `opa` | An empty `AR_OPA_URL` uses the built-in evaluator. What is lost: a tenant's own Rego rules (feature `custom_rego`, off by default). The proof that the built-in evaluator and the Rego agree is two fixtures, which is thin. | `libs/ar_domain/src/ar_domain/policy/engine.py:40-51`, `libs/ar_domain/tests/unit/test_m5_policy.py:59-87` |
| `openbao` | The secrets backend defaults to `db_encrypted`, and Compose never sets the vault backend for the services. The container appears to be unused today. | `libs/ar_common/src/ar_common/settings.py:489`, `libs/ar_domain/src/ar_domain/secrets/cached.py:19-34` |
| `squid` | Used only by computers, for outbound access through a per-computer allow-list. Without it a computer has no outbound access. It goes with `sandbox-manager`. | `libs/ar_domain/src/ar_domain/sandboxes/manager_launch.py:120-127` |
| `clamav` | Already optional. | `compose.yaml:272-276` |

### Dependencies that must stay, as the code is

| Dependency | Why |
|---|---|
| `postgres` | Everything, including Temporal's own two databases. |
| `temporal` | The only run path (OQ-138). Chat turns, routines, document parsing and evals are workflows. It already stores its data in the same Postgres, so it costs one server container. |
| `valkey` | Staging and production refuse to start without it: sessions, sign-in lockout, rate limits and the model circuit breaker live there (OQ-59). Only `AR_ENV=dev` runs without it, and that mode also turns off the production safeguards, so it is not an answer. |
| `seaweedfs` | File bytes go to an S3 store and nothing else. ADR-0014 rejected a filesystem store and Postgres storage. A customer who already has S3 storage can point the product at it and leave this container out. |
| `mcp-gateway` | Every tool call goes through it. The in-process shortcut used in development skips its quota, outbound-access and audit steps, and production refuses that shortcut. |

### Merging processes

- The three workers can very likely run in one process: `libs/ar_testing/src/ar_testing/runtime.py:90-110` already runs runtime, eval and ingest workers together, and no workflow or activity name is used twice.
- `ingest-worker` should stay its own container. Its 11 GB image exists because of Docling and LibreOffice, and merging it would put that weight in every worker.
- The web-facing services cannot simply become one application: each has its own middleware, some routes collide (`/healthz`, `/mcp`), and each builds its own store. Running them as separate servers inside one process works but saves little memory. It is not worth doing first.

## 4. Target

### Core: 9 containers

| Container | Holds |
|---|---|
| `api` | The API, as today |
| `web` | The web app, as today |
| `worker` | `runtime-worker` and `system-worker` in one process (stage 2) |
| `ingest-worker` | Document parsing, as today |
| `mcp-gateway` | The tool-call choke point, as today |
| `postgres`, `valkey`, `temporal`, `seaweedfs` | As today |

### Switched on by the customer

As built in stage 1, a feature is a file, `compose.<feature>.yaml`, not a profile: one file starts the feature's services and sets their addresses on the core, so there is one switch and it cannot be half set. The files are listed in `docs/07-ops/compose.md` section 3a.

| Profile | Adds | When |
|---|---|---|
| `computers` | `sandbox-manager`, `squid` | Agents that use a computer or a browser |
| `channels` | `channels` | Slack, Teams or email |
| `connectors` | `mcp-sql`, and `mcp-openapi` if stage 1 shows it has a use | SQL or OpenAPI connections |
| `policy-opa` | `opa` | A tenant's own Rego rules |
| `vault` | `openbao` | Secrets in a vault instead of the encrypted database column |
| `scan` | `clamav` | Virus scanning of uploads (exists today) |

`model-gateway` and the standalone `sandbox-agent` container are removed if stage 1 confirms they are unused.

The full layout stays available: turning every profile on gives today's install, for a customer who wants to scale parts separately.

### Measured size

Measured in CI: with the two workers in one process the core idles at about 1.5 GiB (it was about 1.9 GiB with them apart), and the six feature services measured add about 0.5 GiB. The table is in `docs/07-ops/compose.md` section 3a. The estimate below was written before the measurement and was too high.

### Expected size (before measurement)

Not measured yet. From the partial figures in section 2, the core should fit in about 3 to 4 GB of memory when idle, plus up to 1 GB while a large document is parsed. Stage 1 replaces this estimate with measurements. Until then the honest recommendation for the core is a machine with 8 GB of memory, and 16 GB with every profile on.

## 5. Stages

One pull request per stage. Each stage ends with a run on a machine that is not the owner's laptop (section 7).

### Stage 1: profiles, proof and measurement (no change to product code)

- Move the optional services in `compose.yaml` out of the `production` profile into the profiles in section 4. The `production` profile becomes the core.
- Make the settings follow: an install without `computers` must start without `AR_SANDBOX_MANAGER_URL`, and say in words that computers are off when an agent asks for one. This is the one product change in the stage (`sandboxes/manager_launch.py:145-150`).
- Prove each "can be left out" finding in section 3 by running the core and exercising it: sign-in, a chat turn with tools, a document upload and question, a routine, an eval. Record what breaks.
- Measure memory for every container, idle and under that load, and write the table into `docs/07-ops/compose.md` with the sizing recommendation.
- Remove `model-gateway` and the standalone `sandbox-agent` only if the run confirms they are unused; otherwise record what uses them.
- Fix what this investigation found on the way, in the same pull request where small, otherwise in open questions:
  - `compose.yaml:20` defaults `AR_ENV` to `dev` even under the `production` profile.
  - Compose fixes the network names (`compose.yaml:517-522`), so two installs on one host share a network. Name them after the project.
  - `mcp-gateway` and the workers never copy `AR_OPA_URL` onto their store (`readmodel/model.py:76`), so they probably already decide with the built-in evaluator while the API asks OPA. One install must decide one way.
  - Docs that have drifted: `docs/07-ops/local-dev.md:23,28,47-52`, OQ-36 in `docs/open-questions.md`.

### Stage 2: one worker process

- A launcher that runs the runtime and system workers in one process, with one health port and each worker keeping its own store. It cannot live in a service package (services do not import each other); it is a new small package or an entry in `ar_common` that loads the workers by name.
- Compose `worker` uses it. The split `runtime-worker` and `system-worker` stay available behind a profile for customers who scale them apart.
- Tests: the existing workflow tests against the merged worker; a chat turn, a routine and an eval on the core install.

### Stage 3: more parity proof for the built-in policy evaluator

Leaving OPA out by default makes the built-in evaluator the one most customers rely on. Extend `policies/fixtures` and `test_fixtures_agree_with_opa` to cover every rule effect, the risk defaults, approvals, four-eyes and argument matching, and run it in CI where OPA is installed.

### Stage 4 (only if the owner chooses it in section 6): fewer dependencies

Each of these is a real product change with its own ADR:

- **Valkey out:** Postgres-backed versions of the session, lockout, rate-limit and circuit-breaker stores, allowed in staging and production. Saves one container.
- **SeaweedFS out:** a filesystem `ObjectStore` for single-machine installs, which reopens ADR-0014. Saves one container and 137 MiB.
- **`mcp-gateway` inside the API process** as a second server on loopback. Saves one container; the gateway's steps stay in the path.

With all three the core is 6 containers: `api`, `web`, `worker`, `ingest-worker`, `postgres`, `temporal`.

## 6. Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | Is the core in section 4 the right default, with the rest as opt-in profiles? | Yes. |
| 2 | OPA off by default, built-in evaluator on? | Yes, with stage 3 done before the default changes. |
| 3 | Remove `model-gateway` if stage 1 confirms nothing uses it? | Yes. Otherwise it is a service every install pays for and none uses. |
| 4 | Go on to stage 4? Which of its three parts? | Decide after stage 1's measurements. Valkey-out is the most valuable; the filesystem store is the most contentious, because it gives up running on more than one machine. |
| 5 | Should the Helm chart get the same core and profiles? | Yes, after Compose, so the two installs stay the same product. Helm is not installed on the development Mac, so this needs a cluster or CI to check. |

## 7. How it is tested

- Never on the owner's laptop. The work needs a machine or a cloud instance with at least 16 GB of memory; the certification handover already names a separate box.
- Each stage runs the core from an empty database with a real model, signs in, and exercises chat with tools, documents, a routine and an eval (strict rule 4).
- Memory is recorded per container, idle and under load, and compared with the stage before.
- The full install (every profile on) is started once per stage to show nothing was lost.
- CI's `compose-smoke` job runs the core; a second job runs every profile on.

## 8. What this plan does not do

- It does not change how many replicas the product can run. The core is a single-machine layout; the split layout remains for scale.
- It does not make document parsing lighter. The 11 GB ingest image and its memory use while parsing are a separate problem; run 6 also saw that worker restart during PDF parsing, cause not yet found.
- It does not finish certification run 6, which is paused until it can run on a suitable machine.
