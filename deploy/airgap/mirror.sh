#!/usr/bin/env bash
# Copy images.txt into $REGISTRY for an air-gapped install.
# PUSH=0 tags locally without pushing. SAVE=bundle.tar docker-saves the set.
set -euo pipefail
registry="${REGISTRY:?set REGISTRY to the air-gapped registry}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
list="$root/deploy/airgap/images.txt"
saved=()
while read -r upstream dest _; do
  if [[ -z "${upstream}" || "${upstream}" == \#* ]]; then
    continue
  fi
  dest="${dest:-$upstream}"
  docker pull "$upstream"
  docker tag "$upstream" "${registry}/${dest}"
  saved+=("${registry}/${dest}")
  if [[ "${PUSH:-1}" == "1" ]]; then
    docker push "${registry}/${dest}"
  fi
done < "$list"
if [[ -n "${SAVE:-}" ]]; then
  docker save -o "$SAVE" "${saved[@]}"
fi
printf 'mirrored %s images into %s\n' "${#saved[@]}" "$registry"
