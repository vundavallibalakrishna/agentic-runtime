#!/usr/bin/env bash
# Install the chart with platform-database isolation on a Calico kind cluster.
# Calico enforces NetworkPolicy. The default kind CNI does not.
# Proof: migrate, ready pods, one gateway tool hop, and a denied instance dial.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
name="${KIND_CLUSTER:-ar-airgap}"
namespace="${AIRGAP_NAMESPACE:-agentic-runtime}"
chart="$root/deploy/helm/agentic-runtime"

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
  arch="$(uname -m)"
  case "$arch" in
    x86_64) kube_arch=amd64 ;;
    aarch64|arm64) kube_arch=arm64 ;;
    *) echo "unsupported arch $arch" >&2; exit 1 ;;
  esac
  curl -fsSL -o /tmp/kubectl "https://dl.k8s.io/release/v1.33.1/bin/linux/${kube_arch}/kubectl"
  chmod +x /tmp/kubectl
  export PATH="/tmp:$PATH"
fi
if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required" >&2
  exit 1
fi

if ! kind get clusters | grep -qx "$name"; then
  cat > /tmp/kind-calico.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: 10.244.0.0/16
  serviceSubnet: 10.96.0.0/12
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            feature-gates: ImageVolume=true
      - |
        kind: ClusterConfiguration
        apiServer:
          extraArgs:
            feature-gates: ImageVolume=true
        scheduler:
          extraArgs:
            feature-gates: ImageVolume=true
        controllerManager:
          extraArgs:
            feature-gates: ImageVolume=true
EOF
  kind create cluster --name "$name" --config /tmp/kind-calico.yaml --image kindest/node:v1.33.1
fi
kubectl config use-context "kind-${name}"

echo "installing Calico"
curl -fsSL -o /tmp/calico.yaml \
  "https://raw.githubusercontent.com/projectcalico/calico/v3.29.3/manifests/calico.yaml"
python3 - <<'PY'
from pathlib import Path
text = Path("/tmp/calico.yaml").read_text(encoding="utf-8")
old = '            # - name: CALICO_IPV4POOL_CIDR\n            #   value: "192.168.0.0/16"'
new = '            - name: CALICO_IPV4POOL_CIDR\n              value: "10.244.0.0/16"'
if old not in text:
    raise SystemExit("calico manifest no longer has the expected pool comment")
Path("/tmp/calico.yaml").write_text(text.replace(old, new, 1), encoding="utf-8")
PY
kubectl apply --server-side -f /tmp/calico.yaml
kubectl -n kube-system rollout status daemonset/calico-node --timeout=10m
kubectl -n calico-system rollout status deployment/calico-kube-controllers --timeout=5m || \
  kubectl -n kube-system rollout status deployment/calico-kube-controllers --timeout=5m

echo "installing CloudNativePG"
kubectl apply --server-side \
  -f "https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.30/releases/cnpg-1.30.1.yaml"
kubectl -n cnpg-system rollout status deployment/cnpg-controller-manager --timeout=10m

echo "building the contract image"
docker build -f images/contract.Dockerfile -t ar-contract:dev .
for repo in ar-api ar-runtime ar-mcp-gateway ar-sandbox-manager ar-model-gateway ar-fake-llm ar-migrate; do
  docker tag ar-contract:dev "${repo}:dev"
done
if ! kind load docker-image ar-api:dev ar-runtime:dev ar-mcp-gateway:dev \
  ar-sandbox-manager:dev ar-model-gateway:dev ar-fake-llm:dev ar-migrate:dev --name "$name"; then
  echo "kind load failed; importing the contract image with ctr"
  tar="$(mktemp)"
  node="${name}-control-plane"
  docker save ar-contract:dev -o "${tar}"
  docker cp "${tar}" "${node}:/root/ar-image.tar"
  docker exec "${node}" ctr --namespace k8s.io images import /root/ar-image.tar
  for repo in ar-api ar-runtime ar-mcp-gateway ar-sandbox-manager ar-model-gateway ar-fake-llm ar-migrate; do
    docker exec "${node}" ctr --namespace k8s.io images tag docker.io/library/ar-contract:dev "docker.io/library/${repo}:dev"
  done
  docker exec "${node}" rm -f /root/ar-image.tar
  rm -f "${tar}"
fi

db_pass="$(openssl rand -hex 18)"
api_ip="$(kubectl get endpoints kubernetes -n default -o jsonpath='{.subsets[0].addresses[0].ip}')"
if [[ -z "$api_ip" ]]; then
  echo "kubernetes endpoint address is empty"
  exit 1
fi
api_cidrs="$(mktemp)"
cat >"$api_cidrs" <<EOF
cluster:
  apiServerCidrs:
    - 10.96.0.0/12
    - ${api_ip}/32
EOF
if ! helm upgrade --install agentic-runtime "$chart" \
  --namespace "$namespace" --create-namespace \
  -f "$chart/values-stage9-contract.yaml" \
  -f "$chart/values-airgap.yaml" \
  -f "$chart/values-airgap-kind.yaml" \
  -f "$api_cidrs" \
  --set "postgres.password=${db_pass}" \
  --timeout 25m --wait; then
  kubectl -n "$namespace" get pods -o wide || true
  kubectl -n "$namespace" describe cluster agentic-runtime-pg || true
  kubectl -n "$namespace" logs -l cnpg.io/cluster=agentic-runtime-pg --all-containers --tail=80 || true
  kubectl -n "$namespace" logs -l app.kubernetes.io/name=temporal --tail=40 || true
  kubectl -n "$namespace" logs job/agentic-runtime-migrate --tail=80 || true
  kubectl -n "$namespace" logs job/agentic-runtime-bootstrap --tail=80 || true
  rm -f "$api_cidrs"
  exit 1
fi
rm -f "$api_cidrs"

echo "checking every workload"
kubectl -n "$namespace" get deploy,sts -o name | while read -r item; do
  kubectl -n "$namespace" rollout status "$item" --timeout=10m
done

AIRGAP_NAMESPACE="$namespace" uv run python scripts/contract_airgap.py
