# Release 1.0 checklist

Chart `1.0.0`. Tag `v1.0.0` runs `.github/workflows/release.yml`, which packages the chart and writes a SHA-256 sidecar. Image signing with cosign is the registry step in `docs/07-ops/ci-cd.md` and runs when the registry credentials are present. This repository's dry run is `uv run python scripts/release.py --dry-run`.

| Check | Result |
|---|---|
| `scripts/check_helm.sh` for every preset | Run before the pull request |
| Fixture DR drill `scripts/dr/restore_drill.sh` | Report in `dr-drills.md` |
| Load probe | `docs/08-quality/reports/load-2026-10-28.md` |
| Security verification from M14 | No accepted risks in that milestone |
| Real Slack workspace | Operator step. Not run in this environment (OQ-48) |
| Real Teams workspace | Operator step. Not run in this environment (OQ-48) |
| Real corporate IdP | Operator step. Dev login and the bundled Keycloak realm are what CI covers |
| Live CloudNativePG PITR into a second namespace | Operator step. The chart sets `archive_timeout=300` and the fixture drill checks the chain |
