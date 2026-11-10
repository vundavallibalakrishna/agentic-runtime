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

helm upgrade --install agentic-runtime deploy/helm/agentic-runtime \
  --namespace "$namespace" --create-namespace \
  -f deploy/helm/agentic-runtime/values-dev.yaml \
  -f deploy/helm/agentic-runtime/values-stage9-contract.yaml \
  --timeout 20m

echo "waiting for api and worker deployments"
kubectl -n "$namespace" rollout status deploy/agentic-runtime-api --timeout=15m
kubectl -n "$namespace" rollout status deploy/agentic-runtime-runtime-worker --timeout=15m
kubectl -n "$namespace" get deploy agentic-runtime-mcp-gateway agentic-runtime-sandbox-manager

uv run python scripts/contract_stage9.py --namespace "$namespace"
