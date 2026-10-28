#!/usr/bin/env bash
# Weekly backup verification entrypoint. Without a cluster it checks the fixture.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
exec "$root/scripts/dr/restore_drill.sh"
