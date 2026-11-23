#!/usr/bin/env bash
# Says whether a change needs the test suite. Writes code=true or code=false to
# GITHUB_OUTPUT. Only a pull request whose every changed file is Markdown under docs/
# is code=false. Anything else, and anything that cannot be worked out, is code=true.
set -euo pipefail
code=true
if [ "${EVENT:-}" = "pull_request" ] && [ -n "${BASE:-}" ] && [ -n "${HEAD:-}" ]; then
  if files="$(git diff --name-only "$BASE...$HEAD" 2>/dev/null)" && [ -n "$files" ]; then
    if ! printf '%s\n' "$files" | grep -Evq '^docs/.*\.md$'; then
      code=false
    fi
  fi
fi
echo "code=$code"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "code=$code" >>"$GITHUB_OUTPUT"
fi
