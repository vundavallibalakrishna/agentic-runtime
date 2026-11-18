#!/usr/bin/env bash
# Live certification. See docs/09-plan/live-certification.md.
# Proof label is live only when AR_LLM_API_KEY is set and every step passes.
# Without a key the scorecard is contract and the live run stays pending.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
# Screenshots use the same Playwright pin as the sandbox browser extra.
# Browsers stay in the checkout. The install must not prune a shared cache.
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$root/.playwright-browsers}"
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"
uv run --with 'playwright==1.64.1' python -m playwright install chromium
exec uv run --with 'playwright==1.64.1' python scripts/certify_live.py "$@"
