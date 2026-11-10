#!/usr/bin/env bash
# Live certification. See docs/09-plan/live-certification.md.
# Proof label is live only when AR_LLM_API_KEY is set and every step passes.
# Without a key the scorecard is contract and the live run stays pending.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
exec uv run python scripts/certify_live.py "$@"
