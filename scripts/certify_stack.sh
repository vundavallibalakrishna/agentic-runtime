#!/usr/bin/env bash
# Certification on a fresh install, in one command. See docs/09-plan/live-certification.md.
#
# Starts the single-node install with every feature on, in the staging environment,
# seeds one tenant with an admin and a reviewer, and runs the certification parts named
# in AR_CERT_PARTS against the tenant's real model. It runs on any machine with Docker
# and 16 GB of memory; the `certification` CI job runs it on a hosted runner.
#
#   AR_CERT_PARTS     any of: live tools agents (default: none, the install is the check)
#   AR_LLM_API_KEY    the model provider's key; required by every part
#   AR_CERT_REPEAT    times each tool flow runs (default 2)
#   AR_CERT_EVIDENCE  where the evidence goes (default var/certification)
#
# It never prints a password or the model key.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

parts="${AR_CERT_PARTS:-}"
evidence="${AR_CERT_EVIDENCE:-var/certification}"
for part in $parts; do
  case "$part" in
    live | tools | agents) ;;
    *)
      echo "AR_CERT_PARTS: '$part' is not a part. Use any of: live tools agents" >&2
      exit 2
      ;;
  esac
done
if [ -n "$parts" ] && [ -z "${AR_LLM_API_KEY:-}" ]; then
  echo "AR_LLM_API_KEY is not set. The parts '$parts' call the tenant's model and cannot run without it." >&2
  exit 2
fi
case " $parts " in
  *" live "*) ;;
  *)
    if [ -n "$parts" ]; then
      echo "AR_CERT_PARTS must include 'live': it connects the tenant's model, which the other parts use." >&2
      exit 2
    fi
    ;;
esac
mkdir -p "$evidence"

# The install's settings. An .env that is already here is somebody's install: it is
# used as it is and never rewritten.
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  uv run python scripts/dev_keys.py
  sed -i.bak 's|^AR_CLAMAV_ADDRESS=.*|AR_CLAMAV_ADDRESS=clamav:3310|' .env
  rm -f .env.bak
elif ! grep -q '^AR_CLAMAV_ADDRESS=clamav:3310$' .env; then
  echo "This checkout has an .env without AR_CLAMAV_ADDRESS=clamav:3310. Add it, or move the file away for a fresh install." >&2
  exit 2
fi
set -a
# shellcheck disable=SC1091
. ./.env
set +a

export AR_ENV=staging
export AR_AUTH_MODE=password
export AR_PASSWORD_LOGIN=true
export AR_DEPLOYMENT_MODE=single_tenant
export AR_FILES_SCANNER=clamav
# Inside a container this machine's own address is the container, never the install.
export AR_EGRESS_ALLOW_LOOPBACK=false
export COMPOSE_FILE="compose.yaml:compose.computers.yaml:compose.channels.yaml:compose.connectors.yaml:compose.opa.yaml:compose.vault.yaml:compose.model-gateway.yaml"
export COMPOSE_PROFILES="production,scan"

export AR_API_URL="http://127.0.0.1:${AR_PORT:-8000}"
export AR_PUBLIC_URL="http://127.0.0.1:${AR_WEB_HOST_PORT:-3000}"
export AR_WEB_URL="$AR_PUBLIC_URL"
export AR_ADMIN_EMAIL="${AR_ADMIN_EMAIL:-admin@cert.local}"
export AR_SECOND_EMAIL="${AR_SECOND_EMAIL:-reviewer@cert.local}"
export AR_SECOND_NAME="${AR_SECOND_NAME:-Cert Reviewer}"
export AR_SECOND_ROLE="${AR_SECOND_ROLE:-approver}"
new_password() { python3 -c 'import secrets; print("Cert-" + secrets.token_hex(16))'; }
export AR_ADMIN_PASSWORD="${AR_ADMIN_PASSWORD:-$(new_password)}"
export AR_SECOND_PASSWORD="${AR_SECOND_PASSWORD:-$(new_password)}"
export AR_CERT_APPROVER_EMAIL="$AR_SECOND_EMAIL"
export AR_CERT_APPROVER_PASSWORD="$AR_SECOND_PASSWORD"
if [ -n "${GITHUB_ACTIONS:-}" ]; then
  echo "::add-mask::$AR_ADMIN_PASSWORD"
  echo "::add-mask::$AR_SECOND_PASSWORD"
fi

state() {
  docker compose ps --all --format 'table {{.Service}}\t{{.Status}}' >"$evidence/compose-ps.txt" 2>&1 || true
  docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' \
    >"$evidence/docker-stats.txt" 2>&1 || true
  # Every line of every service: a fault early in a long run is not in the last lines.
  docker compose logs --no-color >"$evidence/compose-logs.txt" 2>&1 || true
  # Computers are started by the product, not by Compose, so their logs are read by name.
  docker ps --all --filter name=ar-sbx- --format '{{.Names}}\t{{.Status}}' >"$evidence/computers.txt" 2>&1 || true
  for name in $(docker ps --all --filter name=ar-sbx- --format '{{.Names}}'); do
    docker logs --tail 200 "$name" >"$evidence/computer-$name.log" 2>&1 || true
  done
}
trap state EXIT

echo "certification: building the computer image"
docker build -q -f images/sandbox/Dockerfile -t "${AR_SANDBOX_IMAGE:-ar-sandbox:dev}" . >/dev/null

echo "certification: starting the install with every feature on"
docker compose up -d --build --wait --wait-timeout 1800 >"$evidence/compose-up.log" 2>&1 || {
  echo "The install did not start. See compose-up.log and compose-logs.txt in the evidence." >&2
  exit 1
}
curl --fail --silent --show-error -o /dev/null "$AR_API_URL/readyz"
curl --fail --silent --show-error -o /dev/null "$AR_PUBLIC_URL/login"
uv run python scripts/check_no_fake_models.py >"$evidence/no-fake-source.log" 2>&1

echo "certification: seeding one tenant"
AR_DATABASE_URL="postgresql+asyncpg://ar_app:${AR_DB_APP_PASSWORD}@127.0.0.1:${AR_PG_HOST_PORT:-5432}/agentic_runtime" \
  uv run python scripts/seed_tenant.py --slug cert --name Cert \
  --admin-email "$AR_ADMIN_EMAIL" --admin-name "Cert Admin" >"$evidence/seed.log" 2>&1
# A fresh tenant has no model until its admin connects one.
docker compose exec -T postgres psql -U postgres -d agentic_runtime -Atc \
  'select count(*) from model_providers; select count(*) from models;' \
  >"$evidence/providers-after-seed.txt"
if [ "$(tr -d '\n' <"$evidence/providers-after-seed.txt")" != "00" ]; then
  echo "A fresh tenant already has a model provider or a model. See providers-after-seed.txt." >&2
  exit 1
fi

echo "certification: starting a computer and running one command on it"
# A console test of one tool, with no model: the manager starts a computer on the
# sandbox network and the tool gateway runs the command on it.
computer=0
uv run python - >"$evidence/computer-check.log" 2>&1 <<'PY' || computer=$?
import importlib.util
import os
import sys
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("tc", Path("scripts/tool_certification.py"))
tc = importlib.util.module_from_spec(spec)
sys.modules["tc"] = tc
spec.loader.exec_module(tc)
stack = tc.Stack(
    os.environ["AR_API_URL"], os.environ["AR_ADMIN_EMAIL"], os.environ["AR_ADMIN_PASSWORD"]
)
agents = stack.get("/api/v1/agents")
rows = agents.get("items") if isinstance(agents, dict) else agents
assistant = next(row for row in rows if isinstance(row, dict) and row.get("slug") == "assistant")
_made, conversation = stack.post("/api/v1/conversations", agentId=assistant["id"])
# The policy engine reads the new tenant's rules from the API on its next poll. Until
# then a tool call is refused, which is the right answer and not the one being checked.
deadline = time.monotonic() + 180
while True:
    status, body = stack.call(
        "sandbox.exec", {"command": "echo computer-$((40 + 2))"}, str(conversation["id"])
    )
    if "policy_unavailable" not in tc.text_of(body) or time.monotonic() >= deadline:
        break
    time.sleep(5)
print(f"HTTP {status}, result {tc.text_of(body)[:300]}")
if status != 200 or "computer-42" not in tc.text_of(body):
    raise SystemExit(1)
PY
state
if [ "$computer" -ne 0 ]; then
  echo "A computer did not start or did not run the command. See computer-check.log, computers.txt and the computer's log." >&2
  exit 1
fi
state

if [ -z "$parts" ]; then
  echo "certification: the install started and the tenant was seeded. No part was asked for."
  exit 0
fi

export AR_CERT_DOCUMENT="${AR_CERT_DOCUMENT:-$root/docs/00-overview/vision.md}"
export AR_CERT_RESEARCH_QUESTION="${AR_CERT_RESEARCH_QUESTION:-What is the north star of Cura Works, and what must the assistant do when an action is risky?}"
failed=""
run_part() {
  local name="$1"
  shift
  echo "certification: $name"
  local code=0
  "$@" >"$evidence/$name.log" 2>&1 || code=$?
  echo "$code" >"$evidence/$name.exit"
  if [ "$code" -ne 0 ]; then
    failed="$failed $name"
  fi
  state
}

# In this order whatever order they were named in: live connects the tenant's model.
for part in live tools agents; do
  case " $parts " in
    *" $part "*) ;;
    *) continue ;;
  esac
  case "$part" in
    live)
      AR_CERT_OUT="$evidence/live-certification" run_part live bash scripts/certify_live.sh
      ;;
    tools)
      run_part tools uv run python scripts/tool_certification.py \
        --repeat "${AR_CERT_REPEAT:-2}" --out "$evidence/tool-certification"
      ;;
    agents)
      run_part agents uv run python scripts/agent_certification.py \
        --out "$evidence/agent-certification.json"
      ;;
  esac
done

if [ -n "$failed" ]; then
  echo "certification: not passed:$failed. The evidence is in $evidence." >&2
  exit 1
fi
echo "certification: every part passed. The evidence is in $evidence."
