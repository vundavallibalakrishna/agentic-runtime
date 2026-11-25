#!/usr/bin/env bash
# Says what a change needs. Writes two values to GITHUB_OUTPUT.
#
# code=true|false    whether the test suite runs. Only a pull request whose every changed
#                    file is Markdown under docs/ is code=false.
# images=true|false  whether every image is built on its own. The compose smoke already
#                    builds the service, ingest and web images on every pull request that
#                    changes code, so a pull request builds them a second time only when
#                    it changes what that smoke does not exercise: an image's own files,
#                    what is installed into every image, or the two services and the
#                    proxy that only this build covers.
#
# Anything that is not a pull request, and anything that cannot be worked out, is true
# for both: a push to main always runs and builds everything.
set -euo pipefail
code=true
images=true
# Files that make the separate image build worth running on a pull request.
image_files='^(images/|\.dockerignore$|scripts/build_images\.sh$|\.github/workflows/images\.yml$|scripts/ci_changes\.sh$|uv\.lock$|pnpm-lock\.yaml$|(.*/)?pyproject\.toml$|(.*/)?package\.json$|services/sandbox_agent/|services/sandbox_manager/|deploy/compose/squid/)'
if [ "${EVENT:-}" = "pull_request" ] && [ -n "${BASE:-}" ] && [ -n "${HEAD:-}" ]; then
  if files="$(git diff --name-only "$BASE...$HEAD" 2>/dev/null)" && [ -n "$files" ]; then
    if ! printf '%s\n' "$files" | grep -Evq '^docs/.*\.md$'; then
      code=false
    fi
    if ! printf '%s\n' "$files" | grep -Eq "$image_files"; then
      images=false
    fi
  fi
fi
echo "code=$code"
echo "images=$images"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "code=$code"
    echo "images=$images"
  } >>"$GITHUB_OUTPUT"
fi
