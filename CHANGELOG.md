# Changelog

## Unreleased

Customer database connections:

- A URL parameter that can retarget the socket, read a file, or run a startup command is rejected. That includes `host`, `hostaddr`, `port`, `user`, `password`, `dbname` and `options`. `sslmode` must be a libpq mode, and a repeated parameter is rejected.
- Keyword=value connection strings (`host=... dbname=...`) are rejected. Use a `postgresql://` or `mysql://` URL. `postgresql+psycopg` and `mysql+pymysql` are accepted.
- Creating a connection resolves the host in the API process. A name that does not resolve is rejected then, not at the first query.
- With `AR_EGRESS_CLOSED`, a customer database must use TLS. An omitted `sslmode` becomes `verify-full`. `disable`, `allow` and `prefer` are rejected. `AR_DB_STRICT_TLS` defaults to true, so `require` is rejected too until it is set to false. Before upgrading a closed install, set `AR_CA_BUNDLE` or add `sslrootcert=system` to each DSN. Without one of those, verify-full looks for a home-directory root certificate and the connection fails.
- `sslcert` and `sslkey` are read only from `AR_DB_CERT_DIR/<tenant id>/`. If `AR_DB_CERT_DIR` is unset, client certificates are refused. `sslrootcert=system` and the `AR_CA_BUNDLE` file remain allowed. A relative path, an encrypted key, a world-readable key, or a certificate without its key is rejected.
- `AR_PLATFORM_DB_DENY_HOSTS` and `AR_PLATFORM_DB_DENY_CIDRS` refuse customer connections to the platform database services and pod network, on any port. The Helm chart fills the bundled CloudNativePG `-rw`, `-ro`, `-r` and `-pooler` names. `airgap.isolatePlatformDb` limits the runtime worker's port 5432 to the pooler pods.
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
