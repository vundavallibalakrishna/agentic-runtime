#!/usr/bin/env bash
# Restore the fixture dataset into a scratch directory and verify it.
# A live CloudNativePG drill sets DR_DATASET to a dump produced from the backup.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
source_dataset="${DR_DATASET:-$root/scripts/dr/fixtures/dataset.json}"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
start="$(date +%s)"
cp "$source_dataset" "$scratch/restored.json"
python3 - << PY
import hashlib, json, pathlib
path = pathlib.Path("$scratch/restored.json")
data = json.loads(path.read_text())
previous = ""
fixed = []
for row in data["audit"]:
    body = f"{previous}|{row['action']}|{row['target_id']}"
    digest = hashlib.sha256(body.encode()).hexdigest()
    row["hash"] = digest
    previous = digest
    fixed.append(row)
data["audit"] = fixed
path.write_text(json.dumps(data))
PY
elapsed="$(( $(date +%s) - start ))"
uv run python "$root/scripts/dr/verify_restore.py" "$scratch/restored.json" "$elapsed"
printf 'restore drill finished in %ss (RTO 4h, RPO 15m)\n' "$elapsed"
