#!/usr/bin/env python
"""Prove the external agent API runs a real agent end to end, with usage and cost.

Exercises the /v1 integration path in process on the demo tenant with the reasoning alias
pointed at the cert model (the gym's live path, no running stack): mint an agent API key,
then call the one-shot `run_once` (the POST /v1/agents/{slug}:run shape) and assert the
model answered and the reply carries token + cost usage.

  AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/api_integration_proof.py

The cert key is read from the environment and never printed. The service-account key+secret
auth path (/api/v1) is proven by the unit/integration tests; a full HTTP proof of it needs the
running API + Postgres stack.
"""

from __future__ import annotations

import asyncio

from ar_domain.chat.service import demo_id
from ar_domain.evals.gym.live import install_live, live_settings
from ar_domain.exposure import keys, runs
from ar_testing.demo import demo_store


async def run() -> int:
    store = demo_store()
    store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    key, url, model = live_settings()
    install_live(store, demo_id("tenant"), key=key, base_url=url, model=model)

    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    api_key, secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="proof",
    )
    checks: list[tuple[str, bool, str]] = []

    # 1. The agent key is shown once and stored only as a hash.
    checks.append(
        (
            "agent key minted (shown once)",
            secret.startswith("ara_") and api_key.get("secret_hash") not in (None, secret),
            f"prefix={api_key.get('prefix')}",
        )
    )

    # 2. One-shot run through the external path with a real model.
    reply, replayed = await runs.run_once(
        store, api_key, "assistant", "Reply with exactly the word: pong.", [], "proof-1"
    )
    output = str(reply.get("output") or "")
    checks.append(
        (
            "one-shot run answered",
            not replayed and "pong" in output.lower(),
            f"output={output[:60]!r}",
        )
    )

    # 3. The reply carries token + cost usage for the integrator.
    raw_usage = reply.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    checks.append(
        (
            "reply carries usage + cost",
            "cost_micros" in usage and int(usage.get("tokens_out") or 0) > 0,
            f"usage={usage}",
        )
    )

    # 4. Idempotency: the same key replays the same run, no second run.
    again, replayed2 = await runs.run_once(
        store, api_key, "assistant", "Reply with exactly the word: pong.", [], "proof-1"
    )
    checks.append(
        (
            "idempotent replay",
            replayed2 and again.get("id") == reply.get("id"),
            f"replayed={replayed2}",
        )
    )

    passed = sum(1 for _n, ok, _d in checks if ok)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
    print(f"\napi integration proof: {passed}/{len(checks)} (model {model})")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
