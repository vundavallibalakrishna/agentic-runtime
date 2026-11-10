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
# The job controller deletes the pod once the backoff limit is hit, so follow
# the log while the wait is in progress.
kubectl -n "$namespace" logs -f job/agentic-runtime-bootstrap --pod-running-timeout=2m \
  > /tmp/stage9-bootstrap.log 2>&1 &
log_pid=$!
if ! kubectl -n "$namespace" wait --for=condition=complete job/agentic-runtime-bootstrap --timeout=8m; then
  wait "$log_pid" || true
  cat /tmp/stage9-bootstrap.log || true
  job_logs agentic-runtime-bootstrap
  exit 1
fi
kill "$log_pid" >/dev/null 2>&1 || true

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
kubectl -n "$namespace" get deploy agentic-runtime-mcp-gateway agentic-runtime-sandbox-manager

uv run python scripts/contract_stage9.py --namespace "$namespace"
