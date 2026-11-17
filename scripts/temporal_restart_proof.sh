#!/usr/bin/env bash
# Show a Temporal workflow is still there after a history pod is replaced.
# The workflow is one Temporal itself runs in the temporal-system namespace,
# stored in Postgres. Proof label: contract.
set -euo pipefail
namespace="${1:?namespace}"
frontend="agentic-runtime-temporal-frontend"
history="agentic-runtime-temporal-history"

frontend_exec() {
  kubectl -n "$namespace" exec "deploy/${frontend}" -- "$@"
}

echo "waiting for a temporal-system workflow"
workflow_id=""
for _ in $(seq 1 36); do
  raw="$(frontend_exec temporal --address 127.0.0.1:7233 workflow list \
    --namespace temporal-system --limit 20 --output json 2>/dev/null || true)"
  workflow_id="$(printf '%s' "$raw" | python3 -c '
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)
rows = payload if isinstance(payload, list) else payload.get("executions") or payload.get("workflows") or []
for row in rows:
    execution = row.get("execution") if isinstance(row, dict) else None
    if isinstance(execution, dict) and execution.get("workflowId"):
        print(execution["workflowId"])
        break
    if isinstance(row, dict) and row.get("workflowId"):
        print(row["workflowId"])
        break
')"
  if [ -n "$workflow_id" ]; then
    break
  fi
  sleep 5
done
if [ -z "$workflow_id" ]; then
  echo "no temporal-system workflow was listed" >&2
  frontend_exec temporal --address 127.0.0.1:7233 workflow list --namespace temporal-system --limit 5 || true
  exit 1
fi
echo "workflow ${workflow_id}"

pod="$(kubectl -n "$namespace" get pods -l app.kubernetes.io/component=history -o jsonpath='{.items[0].metadata.name}')"
echo "restarting ${pod}"
kubectl -n "$namespace" delete "pod/${pod}" --wait=false
kubectl -n "$namespace" rollout status "deploy/${history}" --timeout=10m
frontend_exec temporal --address 127.0.0.1:7233 operator cluster health
described="$(frontend_exec temporal --address 127.0.0.1:7233 workflow describe \
  --namespace temporal-system --workflow-id "$workflow_id")"
printf '%s\n' "$described" | grep -q "$workflow_id"
echo "workflow survived the history restart"
