# Changelog

## 1.0.0

First shippable release of Agentic Runtime.

- Helm umbrella chart for single-tenant and SaaS, with dev, small, large, load-test, external and air-gap presets.
- Bundled or external Postgres (CloudNativePG or a dev StatefulSet), Valkey, Temporal, Keycloak, OpenBao and SeaweedFS. Qdrant stays off unless enabled.
- Backup CronJobs, a fixture restore drill, and Locust scenarios for the performance budgets.
- Rolling upgrades with a migrate hook, PodDisruptionBudgets and optional Temporal worker build ids.
- Air-gap image list and mirror script.
- Release workflow packages the chart from a version tag.

The product behaviour through M14 (chat, agents, tools, policy, sandboxes, knowledge, memory, skills, routines, channels, quotas, evals and assurance) is included.
