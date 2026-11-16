# Changelog

## Unreleased

Customer database connections:

- A URL parameter that can retarget the socket, read a file, or run a startup command is rejected. That includes `host`, `hostaddr`, `port`, `user`, `password`, `dbname` and `options`. `sslmode` must be a libpq mode, and a repeated parameter is rejected.
- Keyword=value connection strings (`host=... dbname=...`) are rejected. Use a `postgresql://` or `mysql://` URL. `postgresql+psycopg` and `mysql+pymysql` are accepted.
- Creating a connection resolves the host in the API process. A name that does not resolve is rejected then, not at the first query.
- With `AR_EGRESS_CLOSED`, a customer database must use TLS. An omitted `sslmode` becomes `verify-full`. `disable`, `allow` and `prefer` are rejected. There is no migration.

## 1.0.0

First shippable release of Agentic Runtime.

- Helm umbrella chart for single-tenant and SaaS, with dev, small, large, load-test, external and air-gap presets.
- Bundled or external Postgres (CloudNativePG or a dev StatefulSet), Valkey, Temporal, Keycloak, OpenBao and SeaweedFS. Qdrant stays off unless enabled.
- Backup CronJobs, a fixture restore drill, and Locust scenarios for the performance budgets.
- Rolling upgrades with a migrate hook, PodDisruptionBudgets and optional Temporal worker build ids.
- Air-gap image list and mirror script.
- Release workflow packages the chart from a version tag.

The product behaviour through M14 (chat, agents, tools, policy, sandboxes, knowledge, memory, skills, routines, channels, quotas, evals and assurance) is included.
