#!/usr/bin/env bash
# Install values-dev on a local kind cluster without waiting for images.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
name="${KIND_CLUSTER:-ar-m15}"
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
if ! kind get clusters | grep -qx "$name"; then
  kind create cluster --name "$name"
fi
kubectl config use-context "kind-${name}"
helm upgrade --install agentic-runtime "$root/deploy/helm/agentic-runtime" \
  --namespace agentic-runtime --create-namespace \
  -f "$root/deploy/helm/agentic-runtime/values-dev.yaml" \
  --no-hooks
kubectl -n agentic-runtime get deploy,sts,job,cm
if [[ "${KEEP_CLUSTER:-0}" != "1" ]]; then
  kind delete cluster --name "$name"
fi
