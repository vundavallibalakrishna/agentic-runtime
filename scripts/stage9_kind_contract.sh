#!/usr/bin/env bash
# Install the chart on kind with 2 API replicas and 2 workers, then run the
# Stage 9 contract scenarios. Proof label: contract (fake-llm, no customer model).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
name="${KIND_CLUSTER:-ar-stage9}"
namespace="${STAGE9_NAMESPACE:-agentic-runtime}"

if ! command -v kind >/dev/null 2>&1; then
  arch="$(uname -m)"
  case "$arch" in
    x86_64) kind_arch=amd64 ;;
    aarch64|arm64) kind_arch=arm64 ;;
    *) echo "unsupported arch $arch" >&2; exit 1 ;;
  esac
  curl -fsSL -o /tmp/kind "https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-${kind_arch}"
  chmod +x /tmp/kind
  export PATH="/tmp:$PATH"
fi
if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required" >&2
  exit 1
fi
if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required" >&2
  exit 1
fi

if ! kind get clusters | grep -qx "$name"; then
  kind create cluster --name "$name"
fi
kubectl config use-context "kind-${name}"

echo "building the contract image"
docker build -f images/contract.Dockerfile -t ar-contract:dev .
for repo in ar-api ar-runtime ar-mcp-gateway ar-sandbox-manager ar-model-gateway ar-fake-llm ar-migrate; do
  docker tag ar-contract:dev "${repo}:dev"
  kind load docker-image "${repo}:dev" --name "$name"
done

# The migrate Job is a pre-install hook, so it would run before Postgres exists.
# Install the workloads first, migrate once Postgres answers, then bootstrap.
helm upgrade --install agentic-runtime deploy/helm/agentic-runtime \
  --namespace "$namespace" --create-namespace \
  -f deploy/helm/agentic-runtime/values-dev.yaml \
  -f deploy/helm/agentic-runtime/values-stage9-contract.yaml \
  --timeout 15m --no-hooks --wait=false

echo "waiting for Postgres and Valkey"
kubectl -n "$namespace" rollout status statefulset/agentic-runtime-postgres --timeout=10m
kubectl -n "$namespace" rollout status statefulset/agentic-runtime-valkey --timeout=5m

echo "migrating and bootstrapping"
helm template agentic-runtime deploy/helm/agentic-runtime \
  --namespace "$namespace" \
  -f deploy/helm/agentic-runtime/values-dev.yaml \
  -f deploy/helm/agentic-runtime/values-stage9-contract.yaml \
  -s templates/jobs.yaml > /tmp/stage9-jobs.yaml
python3 - << 'PY'
from pathlib import Path
text = Path("/tmp/stage9-jobs.yaml").read_text(encoding="utf-8")
docs = [item for item in text.split("---\n") if item.strip()]
for doc in docs:
    if "name: agentic-runtime-migrate" in doc:
        Path("/tmp/stage9-migrate.yaml").write_text("---\n" + doc, encoding="utf-8")
    if "name: agentic-runtime-bootstrap" in doc:
        Path("/tmp/stage9-bootstrap.yaml").write_text("---\n" + doc, encoding="utf-8")
PY
job_logs() {
  local job="$1"
  kubectl -n "$namespace" get pods -l "job-name=${job}" -o wide || true
  kubectl -n "$namespace" describe "job/${job}" || true
  kubectl -n "$namespace" logs "job/${job}" --tail=200 --request-timeout=20s || true
}

kubectl apply -n "$namespace" -f /tmp/stage9-migrate.yaml
if ! kubectl -n "$namespace" wait --for=condition=complete job/agentic-runtime-migrate --timeout=8m; then
  job_logs agentic-runtime-migrate
  exit 1
fi
kubectl apply -n "$namespace" -f /tmp/stage9-bootstrap.yaml
if ! kubectl -n "$namespace" wait --for=condition=complete job/agentic-runtime-bootstrap --timeout=8m; then
  job_logs agentic-runtime-bootstrap
  exit 1
fi

echo "waiting for api and worker deployments"
kubectl -n "$namespace" rollout status deploy/agentic-runtime-api --timeout=15m
kubectl -n "$namespace" rollout status deploy/agentic-runtime-runtime-worker --timeout=15m
kubectl -n "$namespace" get deploy agentic-runtime-mcp-gateway agentic-runtime-sandbox-manager

uv run python scripts/contract_stage9.py --namespace "$namespace"
