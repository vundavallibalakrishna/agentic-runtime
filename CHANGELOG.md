# Changelog

## Unreleased

Customer database connections:

- A URL parameter that can retarget the socket, read a file, or run a startup command is rejected. That includes `host`, `hostaddr`, `port`, `user`, `password`, `dbname` and `options`. `sslmode` must be a libpq mode, and a repeated parameter is rejected.
- Keyword=value connection strings (`host=... dbname=...`) are rejected. Use a `postgresql://` or `mysql://` URL. `postgresql+psycopg` and `mysql+pymysql` are accepted.
- Creating a connection resolves the host in the API process. A name that does not resolve is rejected then, not at the first query.
- With `AR_EGRESS_CLOSED`, a customer database must use TLS. An omitted `sslmode` becomes `verify-full`. `disable`, `allow` and `prefer` are rejected. `AR_DB_STRICT_TLS` defaults to true, so `require` is rejected too until it is set to false. Before upgrading a closed install, set `AR_CA_BUNDLE` or add `sslrootcert=system` to each DSN. Without one of those, verify-full looks for a home-directory root certificate and the connection fails.
- `sslcert` and `sslkey` are read only from `AR_DB_CERT_DIR/<tenant id>/`. If `AR_DB_CERT_DIR` is unset, client certificates are refused. `sslrootcert=system` and the `AR_CA_BUNDLE` file remain allowed. A relative path, an encrypted key, a world-readable key, or a certificate without its key is rejected.
- `AR_PLATFORM_DB_DENY_HOSTS` and `AR_PLATFORM_DB_DENY_CIDRS` refuse customer connections to the platform database services and pod network, on any port. The Helm chart fills the bundled CloudNativePG `-rw`, `-ro`, `-r` and `-pooler` names, or the StatefulSet service name. The chart cannot discover the cluster pod CIDR: set `cluster.podCIDR` (copied into `AR_PLATFORM_DB_DENY_CIDRS`) when pod IPs must be refused. A malformed CIDR stops the process. Deny names are resolved once and cached; a lookup failure keeps the last addresses. A name that has never resolved is logged and reported by `/readyz` (`platform_db`). It does not refuse every other customer database.
- `airgap.isolatePlatformDb` limits platform-database egress for `api`, `runtime-worker`, `mcp-gateway`, `sandbox-manager`, `system-worker` and `ingest-worker` to the platform path: the CNPG pooler, the StatefulSet pods, or `postgres.externalCidrs`. CNPG instance pods (`cnpg.io/podRole: instance`) are not on that path. `api`, `runtime-worker` and `mcp-gateway` also open `airgap.tenantDbPorts` (default 5432 and 3306) to `airgap.tenantDbCidrs`, because those processes run customer database tools. Other pods are denied the platform database. `postgres.externalCidrs` is granted to the six pods even when isolation is off. An external database with isolation on and no CIDR fails the chart render. If `airgap.egressPorts` includes a tenant database port, the chart excludes `cluster.podCIDR` from those CIDRs, and the render fails when `cluster.podCIDR` is empty. A vector read DSN must use the pooler or the StatefulSet service. The air-gap overlay turns isolation on.
- Underscores are allowed in a customer database hostname because internal DNS and libpq accept them.
- `AR_DB_STRICT_TLS_FLOOR` defaults to `verify-full`, so closed egress also rejects `verify-ca`. Set it to `verify-ca` only for a server addressed by an IP literal. A hostname stays on `verify-full`. `require` stays rejected while `AR_DB_STRICT_TLS` is true.
- A customer-database dial tries at most `AR_DB_MAX_ADDRESSES` (default 4) addresses and stops after `AR_DB_CONNECT_DEADLINE_S` (default 15). The host must be an IP literal or an RFC 1123 name.
- There is no migration.

## 1.0.0

First shippable release of Agentic Runtime.

- Helm umbrella chart for single-tenant and SaaS, with dev, small, large, load-test, external and air-gap presets.
- Bundled or external Postgres (CloudNativePG or a dev StatefulSet), Valkey, Temporal, Keycloak, OpenBao and SeaweedFS. Qdrant stays off unless enabled.
- Backup CronJobs, a fixture restore drill, and Locust scenarios for the performance budgets.
- Rolling upgrades with a migrate hook, PodDisruptionBudgets and optional Temporal worker build ids.
- Air-gap image list and mirror script.
- Release workflow packages the chart from a version tag.

The product behaviour through M14 (chat, agents, tools, policy, sandboxes, knowledge, memory, skills, routines, channels, quotas, evals and assurance) is included.
