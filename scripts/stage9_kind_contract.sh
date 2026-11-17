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
done
if ! kind load docker-image ar-api:dev ar-runtime:dev ar-mcp-gateway:dev \
  ar-sandbox-manager:dev ar-model-gateway:dev ar-fake-llm:dev ar-migrate:dev --name "$name"; then
  # kind load asks containerd for the host's fuse-overlayfs snapshotter, which
  # the node does not have. Import once and retag with the node's snapshotter.
  echo "kind load failed; importing the contract image with ctr"
  tar="$(mktemp)"
  node="${name}-control-plane"
  docker save ar-contract:dev -o "${tar}"
  # The node's /tmp is a tmpfs mounted after the container root, so a copy there disappears.
  docker cp "${tar}" "${node}:/root/ar-image.tar"
  docker exec "${node}" ctr --namespace k8s.io images import /root/ar-image.tar
  for repo in ar-api ar-runtime ar-mcp-gateway ar-sandbox-manager ar-model-gateway ar-fake-llm ar-migrate; do
    docker exec "${node}" ctr --namespace k8s.io images tag docker.io/library/ar-contract:dev "docker.io/library/${repo}:dev"
  done
  docker exec "${node}" rm -f /root/ar-image.tar
  rm -f "${tar}"
fi

# Fresh install with hooks. Migrate and the Temporal schema job are post-install:
# they wait until Postgres accepts the role password, so they do not run first.
passwords="$(mktemp)"
trap 'rm -f "$passwords"' EXIT
uv run python "$root/scripts/write_helm_passwords.py" "$passwords"
chart_args=(
  -f deploy/helm/agentic-runtime/values-dev.yaml
  -f deploy/helm/agentic-runtime/values-stage9-contract.yaml
  -f deploy/helm/agentic-runtime/values-temporal-ha-kind.yaml
  -f "$passwords"
)
echo "pulling the pinned Temporal images"
docker pull temporalio/server:1.32.1
docker pull temporalio/admin-tools:1.32.1
kind load docker-image temporalio/server:1.32.1 temporalio/admin-tools:1.32.1 --name "$name" || true
dump_hooks() {
  kubectl -n "$namespace" get jobs,pods -o wide || true
  for job in agentic-runtime-migrate agentic-runtime-temporal-schema agentic-runtime-bootstrap; do
    kubectl -n "$namespace" logs "job/${job}" --tail=200 || true
  done
}
helm upgrade --install agentic-runtime deploy/helm/agentic-runtime \
  --namespace "$namespace" --create-namespace \
  "${chart_args[@]}" \
  --timeout 20m --wait=false || { dump_hooks; exit 1; }

echo "waiting for Postgres and Valkey"
kubectl -n "$namespace" rollout status statefulset/agentic-runtime-postgres --timeout=10m
kubectl -n "$namespace" rollout status statefulset/agentic-runtime-valkey --timeout=5m

echo "waiting for api and worker deployments"
rollout() {
  local deploy="$1"
  local name="${deploy#agentic-runtime-}"
  if kubectl -n "$namespace" rollout status "deploy/${deploy}" --timeout=15m; then
    return 0
  fi
  kubectl -n "$namespace" get pods -o wide || true
  kubectl -n "$namespace" describe "deploy/${deploy}" || true
  kubectl -n "$namespace" describe pods -l "app.kubernetes.io/name=${name}" || true
  kubectl -n "$namespace" logs -l "app.kubernetes.io/name=${name}" --all-containers --tail=200 || true
  return 1
}
rollout agentic-runtime-api
rollout agentic-runtime-runtime-worker
for component in frontend history matching worker; do
  rollout "agentic-runtime-temporal-${component}"
done
kubectl -n "$namespace" get deploy agentic-runtime-mcp-gateway agentic-runtime-sandbox-manager

echo "upgrading the same release"
helm upgrade agentic-runtime deploy/helm/agentic-runtime \
  --namespace "$namespace" \
  "${chart_args[@]}" \
  --timeout 20m --wait=false || { dump_hooks; exit 1; }
rollout agentic-runtime-api
rollout agentic-runtime-runtime-worker
rollout agentic-runtime-temporal-frontend
bash "$root/scripts/temporal_restart_proof.sh" "$namespace"

uv run python scripts/contract_stage9.py --namespace "$namespace"
