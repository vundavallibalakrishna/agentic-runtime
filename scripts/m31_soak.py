"""Twenty-minute public-API soak. The agent key stays in memory and is not written."""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import psycopg

BASE = os.environ.get("AR_PROOF_API", "http://127.0.0.1:18131")
DSN = os.environ.get("M31_DSN", "postgresql://ar_owner:ar_owner@127.0.0.1:5432/m31_fresh")
MINUTES = float(os.environ.get("M31_SOAK_MINUTES", "20"))
WORKERS = int(os.environ.get("M31_SOAK_WORKERS", "4"))
OUT = Path("/tmp/m31-proof/soak.json")  # noqa: S108


def _session() -> tuple[httpx.Client, str]:
    client = httpx.Client(base_url=BASE, timeout=120.0, follow_redirects=False)
    login = client.post("/api/v1/auth/dev-login", params={"email": "admin@dev.local"})
    if login.status_code not in {200, 302, 303}:
        raise SystemExit(f"login {login.status_code}")
    client.headers["x-csrf-token"] = client.cookies.get("ar_csrf") or ""
    stamp = str(int(time.time()))
    agent = client.post(
        "/api/v1/agents",
        json={
            "slug": f"m31-soak-{stamp}",
            "name": "Soak",
            "visibility": "private",
            "definition": {
                "instructions": "Reply with the single word pong.",
                "model": {"alias": "qwenm31"},
                "budget": {
                    "maxSteps": 2,
                    "maxToolCalls": 0,
                    "maxWallClockS": 60,
                    "maxCostMicros": 2000000,
                    "maxTokens": 64,
                },
            },
        },
    )
    if agent.status_code >= 300:
        raise SystemExit(agent.text[:300])
    agent_id = agent.json()["id"]
    slug = f"m31-soak-{stamp}"
    published = client.post(
        f"/api/v1/agents/{agent_id}:publish",
        json={"changeNote": "soak", "skipEvalGate": True},
    )
    if published.status_code >= 300:
        raise SystemExit(published.text[:300])
    created = client.post(
        f"/api/v1/agents/{agent_id}/api-keys",
        json={"label": "Soak", "rateLimitRpm": 600, "monthlyQuota": 100000},
    )
    if created.status_code >= 300:
        raise SystemExit(created.text[:300])
    return client, slug, str(created.json()["key"])


def _api_pid() -> int:
    return int(os.environ.get("M31_API_PID", "0"))


def _rss(pid: int) -> int:
    if pid <= 0:
        return 0
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except OSError:
        return 0
    return 0


def _connections() -> int:
    with psycopg.connect(DSN) as conn:
        row = conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = 'm31_fresh'"
        ).fetchone()
    return int(row[0] if row else 0)


def _one(slug: str, key: str, index: int) -> tuple[int, float, str]:
    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{BASE}/v1/agents/{slug}/conversations",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
        )
        if response.status_code >= 300:
            return response.status_code, time.perf_counter() - started, "open"
        conversation = response.json()["id"]
        reply = httpx.post(
            f"{BASE}/v1/agents/{slug}/conversations/{conversation}/messages",
            headers={"Authorization": f"Bearer {key}"},
            json={"text": f"Reply with the single word pong. Call {index}."},
            timeout=120.0,
        )
        return reply.status_code, time.perf_counter() - started, "message"
    except httpx.HTTPError as exc:
        return 0, time.perf_counter() - started, type(exc).__name__


def main() -> None:
    _session_client, slug, key = _session()
    pid = _api_pid()
    deadline = time.monotonic() + MINUTES * 60
    samples: list[dict[str, int]] = []
    results: list[tuple[int, float]] = []
    errors: dict[str, int] = {}
    lock = threading.Lock()
    started = time.monotonic()

    def worker(slot: int) -> None:
        del slot
        count = 0
        while time.monotonic() < deadline:
            status, elapsed, kind = _one(slug, key, count)
            with lock:
                results.append((status, elapsed))
                if status != 200:
                    errors[f"{status}:{kind}"] = errors.get(f"{status}:{kind}", 0) + 1
            if status == 429:
                time.sleep(2)
            count += 1

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(worker, slot) for slot in range(WORKERS)]
        while any(not item.done() for item in futures):
            samples.append(
                {
                    "t": int(time.monotonic() - started),
                    "rssKb": _rss(pid),
                    "connections": _connections(),
                    "calls": len(results),
                }
            )
            time.sleep(15)
        for item in futures:
            item.result()
    latencies = sorted(item[1] for item in results)

    def pct(q: float) -> float:
        if not latencies:
            return 0
        index = min(len(latencies) - 1, int(q * len(latencies)))
        return round(latencies[index], 3)

    ok = sum(1 for status, _ in results if status == 200)
    window = max(time.monotonic() - started, 1)
    report = {
        "minutes": round(window / 60, 2),
        "workers": WORKERS,
        "calls": len(results),
        "ok": ok,
        "errorRate": round(1 - (ok / len(results)), 4) if results else 1,
        "throughputPerMin": round(len(results) / (window / 60), 2),
        "p50s": pct(0.50),
        "p95s": pct(0.95),
        "p99s": pct(0.99),
        "errors": errors,
        "rssStartKb": samples[0]["rssKb"] if samples else 0,
        "rssEndKb": samples[-1]["rssKb"] if samples else 0,
        "rssMaxKb": max((item["rssKb"] for item in samples), default=0),
        "connectionsStart": samples[0]["connections"] if samples else 0,
        "connectionsEnd": samples[-1]["connections"] if samples else 0,
        "connectionsMax": max((item["connections"] for item in samples), default=0),
        "samples": samples,
    }
    text = json.dumps(report, indent=2)
    if key in text:
        raise SystemExit("soak report contained the agent key")
    OUT.write_text(text + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))


if __name__ == "__main__":
    main()
