#!/usr/bin/env bash
# Lint, render and schema-check every preset. Spec: docs/09-plan/M15-deployment.md.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
chart="$root/deploy/helm/agentic-runtime"
if ! command -v kubeconform >/dev/null 2>&1; then
  arch="$(uname -m)"
  case "$arch" in
    x86_64) asset=kubeconform-linux-amd64.tar.gz ;;
    aarch64|arm64) asset=kubeconform-linux-arm64.tar.gz ;;
    *) echo "unsupported arch $arch" >&2; exit 1 ;;
  esac
  curl -fsSL -o /tmp/kubeconform.tgz "https://github.com/yannh/kubeconform/releases/download/v0.8.0/${asset}"
  tar -C /tmp -xzf /tmp/kubeconform.tgz kubeconform
  export PATH="/tmp:$PATH"
fi
helm lint "$chart"
presets=(values-dev values-small values-large values-saas values-loadtest values-external values-airgap)
for preset in "${presets[@]}"; do
  helm lint "$chart" -f "$chart/$preset.yaml"
done
render() {
  if [ "$#" -eq 0 ]; then
    helm template agentic-runtime "$chart"
  else
    helm template agentic-runtime "$chart" "$@"
  fi
}
render | kubeconform -kubernetes-version 1.33.0 -ignore-missing-schemas -summary -skip CustomResourceDefinition
for preset in "${presets[@]}"; do
  render -f "$chart/$preset.yaml" | kubeconform -kubernetes-version 1.33.0 -ignore-missing-schemas -summary -skip CustomResourceDefinition
done
uv run python "$root/scripts/check_helm.py"
helm lint "$chart/charts/qdrant"
